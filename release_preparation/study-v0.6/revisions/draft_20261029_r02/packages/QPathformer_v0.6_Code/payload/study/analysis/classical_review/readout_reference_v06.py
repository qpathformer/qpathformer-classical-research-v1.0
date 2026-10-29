"""Independent logical density channels and grouped-measurement arithmetic.

No production imports, file reads, test population access or gate authorization.
Logical matrix order is |q0 q1>, so q0 is the most significant index bit.
Qiskit count strings must be interpreted using the declared physical-wire map.
"""
import numpy as np
import ast
import re

I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex)
Y=np.array([[0,-1j],[1j,0]],complex);Z=np.diag([1.,-1.]).astype(complex)
CX=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],complex)
Q0=np.array([1.,1.,-1.,-1.]);Q1=np.array([1.,-1.,1.,-1.])
MOMENT_MATRICES=(np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z))

def need(condition,message):
    if not condition:raise ValueError(message)
def ry(t):
    c,s=np.cos(t/2),np.sin(t/2);return np.array([[c,-s],[s,c]],complex)
def rz(t):return np.diag([np.exp(-.5j*t),np.exp(.5j*t)])
def on(g,q):return np.kron(g,I) if q==0 else np.kron(I,g)
def evolve(rho,u):return u@rho@u.conj().T
def depolarize(rho,p,q=None):
    need(np.isfinite(p) and 0<=p<=1,'Depolarizing strength outside registered physical interval')
    if q is None:return (1-p)*rho+p*np.eye(4)/4
    need(q in (0,1),'Unknown qubit')
    # Local Pauli twirl, algebraically rho -> (1-p)rho+p(I/2 tensor partial-trace).
    return (1-3*p/4)*rho+(p/4)*sum(evolve(rho,on(g,q)) for g in (X,Y,Z))
def check_density(rho):
    need(np.asarray(rho).shape==(4,4) and np.isfinite(rho).all(),'Invalid density matrix')
    need(np.max(abs(rho-rho.conj().T))<2e-12 and abs(np.trace(rho)-1)<2e-12,'Density normalization/Hermiticity changed')
    need(np.linalg.eigvalsh(rho).min()>=-2e-12,'Density positivity changed')
def core_density(x,angles,one_qubit=0.,cx_noise=0.):
    x=np.asarray(x,float);angles=np.asarray(angles,float)
    need(x.shape==(2,) and angles.shape==(2,2,2) and np.isfinite(x).all() and np.isfinite(angles).all(),'Invalid input/core')
    rho=np.zeros((4,4),complex);rho[0,0]=1
    for layer in range(2):
        for q in (0,1):rho=depolarize(evolve(rho,on(ry(np.pi*x[q]),q)),one_qubit,q)
        for q in (0,1):
            rho=depolarize(evolve(rho,on(ry(angles[layer,q,0]),q)),one_qubit,q)
            rho=depolarize(evolve(rho,on(rz(angles[layer,q,1]),q)),one_qubit,q)
        rho=depolarize(evolve(rho,CX),cx_noise)
    check_density(rho);return rho
def moments(rho):
    check_density(rho)
    return np.array([np.trace(rho@op).real for op in MOMENT_MATRICES])
def bit_flip_joint(joint,rate):
    p=np.asarray(joint,float);need(p.shape==(4,) and np.isfinite(p).all() and np.all(p>=-2e-12),'Invalid joint distribution')
    need(abs(p.sum()-1)<2e-12 and np.isfinite(rate) and 0<=rate<=1,'Invalid readout normalization/rate')
    transition=np.array([[1-rate,rate],[rate,1-rate]])
    return np.kron(transition,transition)@p
def setting_distribution(rho,setting,one_qubit=0.,readout_flip=0.):
    need(setting in ('XX','ZZ','legacy_q0'),'Unregistered measurement setting')
    rho=np.array(rho,copy=True)
    if setting=='XX':
        for q in (0,1):rho=depolarize(evolve(rho,on(ry(-np.pi/2),q)),one_qubit,q)
    elif setting=='legacy_q0':rho=depolarize(evolve(rho,on(ry(np.pi/2),0)),one_qubit,0)
    check_density(rho);joint=np.diag(rho).real
    # Remove only tiny negative roundoff, then normalize as a probability vector.
    need(joint.min()>=-2e-12,'Nonphysical joint probabilities');joint=np.maximum(joint,0);joint=joint/joint.sum()
    return bit_flip_joint(joint,readout_flip)
def grouped_moments(xx,zz):
    xx=np.asarray(xx,float);zz=np.asarray(zz,float)
    need(xx.shape==zz.shape==(4,),'Four joint outcomes required per setting')
    return np.array([xx@Q0,xx@Q1,zz@Q0,zz@Q1,zz@(Q0*Q1)])
def apply_head(method,bank_parameters,features):
    theta=np.asarray(bank_parameters,float);f=np.asarray(features,float)
    need(f.shape==(5,) and np.isfinite(f).all(),'Five moments required')
    if method=='q2_kmeans':return float((1+f[0])/2),None
    if method=='qscalar_kmeans':head=theta[8:];need(head.shape==(2,),'Scalar head packing differs');z=float(head[0]*f[0]+head[1])
    elif method=='qmulti_kmeans':head=theta[8:];need(head.shape==(6,),'Multi head packing differs');z=float(head[:5]@f+head[5])
    elif method=='qfrozen_kmeans':need(theta.shape==(6,),'Frozen head packing differs');z=float(theta[:5]@f+theta[5])
    else:raise ValueError('Not a quantum readout arm')
    return float(np.exp(-np.logaddexp(0.,-z))),z
def moments_from_counts(xx_counts,zz_counts):
    a=np.asarray(xx_counts);b=np.asarray(zz_counts)
    need(a.shape==b.shape==(4,) and a.dtype.kind in 'iu' and b.dtype.kind in 'iu' and np.all(a>=0) and np.all(b>=0) and a.sum()>0 and b.sum()>0,'Invalid joint count arrays')
    return grouped_moments(a/a.sum(),b/b.sum())
def qiskit_count_vector(counts,logical_q0_wire=1):
    """Translate c1c0 strings; producer maps logicalq0 to wire1 (already MSB)."""
    need(logical_q0_wire in (0,1),'Invalid logical-to-physical map')
    result=np.zeros(4,dtype=np.int64)
    for text,count in counts.items():
        need(text in ('00','01','10','11') and isinstance(count,(int,np.integer)) and count>=0,'Invalid two-bit counts')
        q0=int(text[1-logical_q0_wire]);q1=int(text[logical_q0_wire])
        logical=2*q0+q1;result[logical]+=count
    return result

# Native snapshot reference uses physical LSB indexing, unlike logical on(g,q).
# No Qiskit/Aer/production imports: serialized channel mixtures are reconstructed
# directly and checked against every exported SuperOp, not trusted as an oracle.
def embed_native(local,qubits,width=2):
    qubits=tuple(qubits);local=np.asarray(local,complex);dim=1<<width;small=1<<len(qubits)
    need(len(set(qubits))==len(qubits) and all(0<=q<width for q in qubits),'Bad native target')
    need(local.shape==(small,small),'Local native matrix shape differs')
    out=np.zeros((dim,dim),complex);mask=sum(1<<q for q in qubits)
    for j in range(dim):
        local_j=sum(((j>>q)&1)<<k for k,q in enumerate(qubits))
        for local_i in range(small):
            i=(j&~mask)|sum(((local_i>>k)&1)<<q for k,q in enumerate(qubits))
            out[i,j]=local[local_i,local_j]
    return out

def noise_instruction(rho,instruction,width):
    name=instruction['name'];targets=instruction['qubits']
    if name=='reset':
        need(len(targets)==1,'Only single-qubit reset supported')
        matrices=(np.array([[1,0],[0,0]],complex),np.array([[0,1],[0,0]],complex))
        return sum(evolve(rho,embed_native(k,targets,width)) for k in matrices)
    if name in ('id','x','y','z'):
        need(len(targets)==1,'Single Pauli gate target differs');local={'id':I,'x':X,'y':Y,'z':Z}[name]
    elif name=='pauli':
        word=instruction['params'][0];need(isinstance(word,str) and len(word)==len(targets),'Pauli string differs')
        local=np.ones((1,1),complex)
        for ch in word:
            need(ch in 'IXYZ','Unsupported Pauli');local=np.kron(local,{'I':I,'X':X,'Y':Y,'Z':Z}[ch])
    else:raise ValueError('Unsupported serialized native channel instruction: '+name)
    return evolve(rho,embed_native(local,targets,width))

def reconstruct_superop(error):
    need(error.get('type')=='qerror','Quantum error expected')
    qubits=error['gate_qubits'];need(qubits and all(len(q)==len(qubits[0]) for q in qubits),'Error target widths differ')
    width=len(qubits[0]);need(width in (1,2),'Only one/two-qubit snapshot channels supported')
    weights=np.asarray(error['probabilities'],float);sequences=error['instructions']
    need(len(weights)==len(sequences) and np.isfinite(weights).all() and weights.min()>=0 and abs(weights.sum()-1)<2e-12,'Invalid channel mixture')
    d=1<<width;out=np.zeros((d*d,d*d),complex)
    for column in range(d*d):
        basis=np.zeros((d,d),complex);basis[column%d,column//d]=1
        result=np.zeros_like(basis)
        for weight,sequence in zip(weights,sequences):
            rho=basis.copy()
            for instruction in sequence:rho=noise_instruction(rho,instruction,width)
            result+=weight*rho
        out[:,column]=result.reshape(-1,order='F')
    return out

def apply_local_superop(rho,channel,qubits,width=2):
    """Apply a column-vectorized local channel by explicit density indices."""
    d=1<<width;qubits=tuple(qubits);s=1<<len(qubits)
    need(rho.shape==(d,d) and np.asarray(channel).shape==(s*s,s*s),'Density/channel dimensions differ')
    mask=sum(1<<q for q in qubits);local=lambda i:sum(((i>>q)&1)<<k for k,q in enumerate(qubits))
    out=np.zeros_like(rho,dtype=complex)
    for i in range(d):
        aa=[a for a in range(d) if (a&~mask)==(i&~mask)]
        for j in range(d):
            bb=[b for b in range(d) if (b&~mask)==(j&~mask)]
            out[i,j]=sum(channel[local(i)+s*local(j),local(a)+s*local(b)]*rho[a,b] for a in aa for b in bb)
    return out

def numeric_expression(text):
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return float(n.value)
        if isinstance(n,ast.Name) and n.id=='pi':return float(np.pi)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return (1 if isinstance(n.op,ast.UAdd) else -1)*visit(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            return a/b
        raise ValueError('Unsupported QASM numeric expression')
    value=visit(ast.parse(text,mode='eval').body);need(np.isfinite(value),'Nonfinite QASM angle');return value

def parse_native_qasm(text):
    width=None;operations=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('//') or line in ('OPENQASM 2.0;','include "qelib1.inc";'):continue
        m=re.fullmatch(r'qreg q\[(\d+)\];',line)
        if m:need(width is None,'Duplicate qreg');width=int(m[1]);continue
        m=re.fullmatch(r'(rz|sx|x|id|cx)(?:\(([^()]*)\))? (q\[\d+\](?:,q\[\d+\])?);',line)
        need(m is not None,'Unsupported native QASM instruction: '+line)
        name,angle,targets=m.groups();qs=tuple(int(v) for v in re.findall(r'q\[(\d+)\]',targets))
        need(all(q in (0,1) for q in qs),'Unexpected active idle wire')
        need(len(qs)==(2 if name=='cx' else 1) and len(set(qs))==len(qs),'Native gate target count differs')
        need((angle is not None)==(name=='rz'),'Native angle differs')
        operations.append((name,qs,None if angle is None else numeric_expression(angle)))
    need(width==5,'Retained native target must have width five');return operations

def native_gate(name,targets,angle):
    if name=='cx':
        # Local bit0 is the control, local bit1 the target.
        local=np.zeros((4,4),complex)
        for j in range(4):local[j^(((j&1)<<1)),j]=1
    else:local={'sx':.5*np.array([[1+1j,1-1j],[1-1j,1+1j]]),'x':X,'id':I}.get(name)
    if name=='rz':local=rz(angle)
    need(local is not None,'Unsupported native ideal gate');return embed_native(local,targets,2)

def native_density(operations,channel_map=None):
    rho=np.zeros((4,4),complex);rho[0,0]=1
    for name,targets,angle in operations:
        rho=evolve(rho,native_gate(name,targets,angle))
        if channel_map is not None and (name,targets) in channel_map:
            rho=apply_local_superop(rho,channel_map[(name,targets)],targets)
    check_density(rho);return rho

def asymmetric_readout(joint,matrices):
    """Explicit P(observed1,observed0)=sum_true T1*T0*P(true1,true0)."""
    result=np.zeros(4)
    for truth in range(4):
        for observed in range(4):
            result[observed]+=joint[truth]*matrices[1][truth//2,observed//2]*matrices[0][truth%2,observed%2]
    return result
