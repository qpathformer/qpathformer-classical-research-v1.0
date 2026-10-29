"""Native-gate execution helpers for a retained five-qubit device snapshot.

No provider/service/authentication or calibration refresh. The physical pair
is fixed to(0,1); compiler routing is disabled and unexpected mapping rejected.
Readout matrices use rows=true bit and columns=observed bit.
"""
import numpy as np
from qiskit import transpile
from qiskit.quantum_info import SuperOp
from qiskit_aer.noise import NoiseModel
from qiskit_aer.noise import QuantumError
import device_snapshot


def load_runtime():
    backend=device_snapshot.load_backend()
    noise=NoiseModel.from_backend(backend)
    serialized=noise.to_dict(serializable=True)
    readout={}
    for error in serialized['errors']:
        if error.get('type')!='roerror':continue
        targets=error.get('gate_qubits')
        if not targets or any(len(q)!=1 for q in targets):
            raise ValueError('Only explicit single-physical-qubit readout errors are supported')
        transition=np.asarray(error['probabilities'],dtype=float)
        if transition.shape!=(2,2) or not np.isfinite(transition).all() or np.any(transition<0) or np.max(abs(transition.sum(axis=1)-1))>2e-12:
            raise ValueError('Invalid snapshot readout transition')
        for (qubit,) in targets:
            if int(qubit) in readout:raise ValueError('Duplicate physical readout transition')
            readout[int(qubit)]=transition.copy()
    if not all(q in readout for q in (0,1)):
        raise ValueError('The fixed physical pair must have explicit snapshot readout transitions')
    return backend,noise,serialized,readout


def compile_native(circuit,backend,seed_transpiler,optimization_level=1):
    if circuit.num_qubits!=2 or circuit.num_clbits:
        raise ValueError('Expected unmeasured two-qubit logical circuit')
    compiled=transpile(circuit,backend=backend,initial_layout=[0,1],routing_method='none',
                       optimization_level=optimization_level,seed_transpiler=seed_transpiler)
    if compiled.num_qubits!=5:raise ValueError('Expected full five-qubit snapshot target')
    mapping=compiled.layout.final_index_layout(filter_ancillas=True)
    if mapping!=[0,1]:raise ValueError('Snapshot compilation changed the fixed logical-to-physical map')
    active=sorted({compiled.find_bit(q).index for inst in compiled.data for q in inst.qubits})
    if any(q not in (0,1) for q in active):raise ValueError('Unexpected gate on an idle snapshot qubit')
    return compiled,{'logical_wire_to_physical':[0,1],'logical_q0_physical':1,'logical_q1_physical':0,
                     'classical_bit_to_physical':[0,1],'count_order':['00','01','10','11'],
                     'physical_width':5,'active_physical_qubits':active,'routing_method':'none'}


def marginal_pair(full_probabilities):
    p=np.asarray(full_probabilities,dtype=float)
    if p.shape!=(32,) or not np.isfinite(p).all() or np.min(p)<-2e-12 or abs(p.sum()-1)>2e-12:
        raise ValueError('Expected normalized five-qubit probabilities')
    # Physical0 is the least significant bit; physical1 is the next bit.
    # The resulting order is q0q1=physical1,physical0.
    joint=p.reshape(8,4).sum(axis=0)
    joint=np.clip(joint,0,1)
    return joint/joint.sum()


def apply_readout(joint,readout):
    joint=np.asarray(joint,dtype=float)
    if joint.shape!=(4,) or np.min(joint)<0 or abs(joint.sum()-1)>2e-12:raise ValueError('Invalid two-qubit joint')
    transition=np.kron(np.asarray(readout[1]).T,np.asarray(readout[0]).T)
    observed=transition@joint
    return observed/observed.sum()


def quantum_channel_tables(noise):
    """Export post-gate local quantum channels for an independent density audit."""
    arrays={};records=[];identities=set()
    for error in noise.to_dict()['errors']:
        if error.get('type')!='qerror':continue
        targets=error.get('gate_qubits');operations=error.get('operations')
        if not targets or not operations:raise ValueError('Explicit local noise targets and operations required')
        channel=SuperOp(QuantumError.from_dict(error)).data
        key='channel_'+str(len(arrays)).zfill(3);arrays[key]=np.asarray(channel,dtype=np.complex128)
        for qubits in targets:
            for operation in operations:
                identity=(operation,tuple(qubits))
                if identity in identities:raise ValueError('Duplicate native quantum channel mapping')
                identities.add(identity)
                records.append({'operation':operation,'physical_qubits':list(qubits),'array_key':key,
                                'num_qubits':len(qubits),'shape':list(channel.shape)})
    return arrays,{'channels':records,'convention':'Qiskit SuperOp column-vectorized density; local bit0 is the first listed physical qubit; channel applies after the native ideal gate.',
                   'absent_gate_rule':'A native instruction without a mapped error has an identity post-gate channel; no idle or delay noise added.'}
