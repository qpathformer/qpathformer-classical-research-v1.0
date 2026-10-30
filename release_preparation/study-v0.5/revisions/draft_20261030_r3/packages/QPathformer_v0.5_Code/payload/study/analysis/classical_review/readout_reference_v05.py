"""Independent logical density channels and grouped-measurement arithmetic.

No production imports, file reads, test population access or gate authorization.
Logical matrix order is |q0 q1>, so q0 is the most significant index bit.
Qiskit count strings must be interpreted using the declared physical-wire map.
"""
import numpy as np

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
