"""Local Qiskit mapping only. Logical q0 maps to wire1, q1 to wire0.

This yields Operator row/column order |q0 q1>. No IBM provider, backend lookup,
cloud credentials, hardware ISA or network function is present.
"""
import numpy as np
from qiskit import QuantumCircuit


def selected_circuit_parameters(method,parameters,depth,hash_route,kmeans_route):
    p=np.asarray(parameters,float)
    if method=='encoding1':return p.reshape(1,2,2),1,True,np.pi/2
    if method=='readout1':return p[:4].reshape(1,2,2),1,False,float(p[4])
    if method=='kmeans40':
        k=int(kmeans_route)
        if not 0<=k<5:raise ValueError('Invalid frozen route')
        return p[k*8:(k+1)*8].reshape(2,2,2),2,False,np.pi/2
    raise ValueError('Only predeclared readiness methods are allowed')


def build_circuit(x,bank,depth,encoding=False,beta=np.pi/2,measure=False):
    x=np.asarray(x,float);bank=np.asarray(bank,float)
    if x.shape!=(2,) or bank.shape!=(depth,2,2) or not np.isfinite(x).all() or not np.isfinite(bank).all() or not np.isfinite(beta):raise ValueError('Invalid circuit inputs')
    qc=QuantumCircuit(2,1) if measure else QuantumCircuit(2)
    for layer in range(depth):
        for logical in range(2):
            wire=1-logical
            qc.ry(float(np.pi*x[logical]),wire)
            if encoding:qc.rz(float(np.pi*x[logical]/2),wire)
            qc.ry(float(bank[layer,logical,0]),wire);qc.rz(float(bank[layer,logical,1]),wire)
        qc.cx(1,0)
    qc.ry(float(beta),1)
    if measure:qc.measure(1,0)
    return qc


def phase_aligned_error(actual,expected):
    a,b=np.asarray(actual),np.asarray(expected)
    overlap=np.vdot(b.ravel(),a.ravel())
    phase=overlap/abs(overlap) if abs(overlap)>0 else 1.
    return float(np.max(abs(a-phase*b)))
