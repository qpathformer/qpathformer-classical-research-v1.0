"""Independent explicit matrix oracle. No production circuit/gate imports."""
import numpy as np


def unitary(x,bank,depth,encoding=False,beta=np.pi/2):
    def y(a):
        return np.array([[np.cos(a/2),-np.sin(a/2)],[np.sin(a/2),np.cos(a/2)]],dtype=complex)
    def z(a):
        return np.diag([np.exp(-1j*a/2),np.exp(1j*a/2)])
    identity=np.eye(2,dtype=complex)
    controlled=np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]],dtype=complex)
    u=np.eye(4,dtype=complex)
    for layer in range(int(depth)):
        for q in range(2):
            sequence=[y(np.pi*x[q])]
            if encoding: sequence.append(z(np.pi*x[q]/2))
            sequence += [y(bank[layer,q,0]),z(bank[layer,q,1])]
            for gate in sequence:
                u=(np.kron(gate,identity) if q==0 else np.kron(identity,gate))@u
        u=controlled@u
    return np.kron(y(beta),identity)@u


def probability(x,bank,depth,encoding=False,beta=np.pi/2):
    state=unitary(x,bank,depth,encoding,beta)[:,0]
    return float(abs(state[2])**2+abs(state[3])**2)


def analytic_d1(x,bank,beta=np.pi/2):
    a0,a1=np.pi*x+bank[0,:,0]
    b0,b1=bank[0,:,1]
    xx=np.sin(a0)*np.cos(b0)*np.sin(a1)*np.cos(b1)
    return float((1-np.cos(beta)*np.cos(a0)+np.sin(beta)*xx)/2)
