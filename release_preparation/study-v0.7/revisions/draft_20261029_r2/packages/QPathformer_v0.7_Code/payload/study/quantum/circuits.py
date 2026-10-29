"""v0.3 vectorized two-qubit circuits, logical basis |q0 q1>.

Derived from the preserved v0.2 NumPy production circuit. Encoding is RY(pi*x)
in EVERY layer; encoding1 adds fixed feature RZ(pi*x/2) between feature RY and
trainable RY. Readout is final RY(beta) q0 and P(q0=1).
"""
import numpy as np


def inputs(x, bank, depth):
    x, bank = np.asarray(x, float), np.asarray(bank, float)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError("x must be finite N by 2")
    if bank.ndim != 3 or bank.shape[1:] != (2,2) or not 1 <= len(bank) <= 4 or not np.isfinite(bank).all():
        raise ValueError("bank must be finite [1..4,2,2]")
    raw = np.broadcast_to(np.asarray(depth), (len(x),))
    d = raw.astype(int)
    if np.any(raw != d) or np.any(d < 1) or np.any(d > len(bank)):
        raise ValueError("invalid depth")
    return x, bank, d


def ry(state, angle, qubit):
    angle = np.broadcast_to(np.asarray(angle), (len(state),))
    c, s = np.cos(angle/2), np.sin(angle/2)
    for i,j in (((0,2),(1,3)) if qubit == 0 else ((0,1),(2,3))):
        a,b = state[:,i].copy(),state[:,j].copy()
        state[:,i],state[:,j] = c*a-s*b,s*a+c*b


def rz(state, angle, qubit):
    phase = np.exp(.5j*np.broadcast_to(np.asarray(angle), (len(state),)))
    zero,one = (((0,1),(2,3)) if qubit == 0 else ((0,2),(1,3)))
    state[:,zero] *= phase.conj()[:,None]
    state[:,one] *= phase[:,None]


def evolve(x,bank,d,state,encoding=False,beta=np.pi/2):
    if not np.isfinite(beta): raise ValueError("nonfinite readout")
    for layer in range(len(bank)):
        chosen=np.flatnonzero(d>layer)
        if not len(chosen): break
        a=state[chosen].copy()
        for q in (0,1):
            ry(a,np.pi*x[chosen,q],q)
            if encoding: rz(a,np.pi*x[chosen,q]/2,q)
            ry(a,bank[layer,q,0],q)
            rz(a,bank[layer,q,1],q)
        state[chosen]=a[:,[0,1,3,2]]
    ry(state,beta,0)
    return state


def predict(x,bank,depth,encoding=False,beta=np.pi/2):
    x,bank,d=inputs(x,bank,depth)
    state=np.zeros((len(x),4),dtype=np.complex128);state[:,0]=1
    state=evolve(x,bank,d,state,encoding,beta)
    return np.clip(np.sum(np.abs(state[:,2:])**2,axis=1),0.,1.)


def unitary(x,bank,depth,encoding=False,beta=np.pi/2):
    x,bank,d=inputs(np.repeat(np.asarray(x)[None],4,axis=0),bank,depth)
    return evolve(x,bank,d,np.eye(4,dtype=np.complex128),encoding,beta).T


def jacobian(x,bank,depth,encoding=False,beta=np.pi/2,train_readout=False):
    """Each trained angle occurs once; shift the gate's angle by +/-pi/2."""
    x,bank,d=inputs(x,bank,depth)
    jac=np.zeros((len(x),bank.size+int(train_readout)))
    for layer in range(len(bank)):
        ids=np.flatnonzero(d>layer)
        if not len(ids): continue
        for q in (0,1):
            for axis in (0,1):
                plus,minus=bank.copy(),bank.copy()
                plus[layer,q,axis]+=np.pi/2;minus[layer,q,axis]-=np.pi/2
                j=layer*4+q*2+axis
                jac[ids,j]=.5*(predict(x[ids],plus,d[ids],encoding,beta)-predict(x[ids],minus,d[ids],encoding,beta))
    if train_readout:
        jac[:,-1]=.5*(predict(x,bank,d,encoding,beta+np.pi/2)-predict(x,bank,d,encoding,beta-np.pi/2))
    return jac


def work(depth,encoding=False,train_readout=False,gradient=False):
    """Counts actual per-record full forward/shift circuit and gate executions."""
    d=np.asarray(depth,dtype=np.int64).ravel()
    repeats=1+8*d+2*int(train_readout) if gradient else np.ones_like(d)
    layers=int(np.sum(d*repeats));examples=int(np.sum(repeats))
    return {"forward_circuit_examples":len(d),"shift_circuit_examples":examples-len(d),
            "circuit_examples":examples,"layer_applications":layers,
            "feature_ry_gates":2*layers,"feature_rz_gates":2*layers*int(encoding),
            "trainable_ry_gates":2*layers,"trainable_rz_gates":2*layers,
            "cx_gates":layers,"readout_ry_gates":examples,"bank_record_visits":len(d)}


def core_state(x, bank):
    """v0.5 D2 state BEFORE the legacy fixed readout; no extra rotation."""
    x, bank, d = inputs(x, bank, 2)
    if len(bank) != 2: raise ValueError('v0.5 core must have two layers')
    state = np.zeros((len(x), 4), dtype=np.complex128); state[:, 0] = 1
    for layer in range(2):
        for q in (0, 1):
            ry(state, np.pi*x[:, q], q)
            ry(state, bank[layer, q, 0], q)
            rz(state, bank[layer, q, 1], q)
        state = state[:, [0, 1, 3, 2]]
    return state


def moments(x, bank, count=5):
    """Ordered X0,X1,Z0,Z1,Z0Z1; scalar mode computes only X0."""
    if count not in (1, 5): raise ValueError('Moment count must be1 or5')
    a = core_state(x, bank)
    x0 = 2*np.real(a[:, 0].conj()*a[:, 2]+a[:, 1].conj()*a[:, 3])
    if count == 1: return x0[:, None]
    x1 = 2*np.real(a[:, 0].conj()*a[:, 1]+a[:, 2].conj()*a[:, 3])
    b = np.abs(a)**2
    return np.column_stack((x0, x1, b[:,0]+b[:,1]-b[:,2]-b[:,3],
                            b[:,0]-b[:,1]+b[:,2]-b[:,3],
                            b[:,0]-b[:,1]-b[:,2]+b[:,3]))


def moment_jacobian(x, bank, count=5):
    """Return N-by-8-by-count exact parameter-shift derivatives."""
    x, bank, _ = inputs(x, bank, 2)
    out = np.empty((len(x), 8, count), dtype=np.float64)
    for j in range(8):
        plus, minus = bank.copy(), bank.copy()
        plus.ravel()[j] += np.pi/2; minus.ravel()[j] -= np.pi/2
        out[:, j, :] = .5*(moments(x, plus, count)-moments(x, minus, count))
    return out
