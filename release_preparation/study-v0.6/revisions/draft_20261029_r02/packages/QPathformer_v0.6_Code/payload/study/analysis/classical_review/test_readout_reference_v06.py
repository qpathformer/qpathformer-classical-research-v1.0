"""Independent native-channel semantics on synthetic states only."""
import unittest
import numpy as np
import readout_reference_v06 as r

class NativeReferenceTests(unittest.TestCase):
    def test_asymmetric_readout_uses_true_rows_not_transpose_convention(self):
        matrices={0:np.array([[.9,.1],[.3,.7]]),1:np.array([[.6,.4],[.2,.8]])}
        for truth in range(4):
            p=np.eye(4)[truth]
            expected=np.kron(matrices[1][truth//2],matrices[0][truth%2])
            np.testing.assert_allclose(r.asymmetric_readout(p,matrices),expected,atol=0,rtol=0)
        self.assertGreater(np.max(abs(r.asymmetric_readout(np.eye(4)[0],matrices)-np.kron(matrices[1],matrices[0])@np.eye(4)[0])),.1)

    def test_cx_orientation_and_single_physical_bit(self):
        for targets in ((0,1),(1,0)):
            u=r.native_gate('cx',targets,None)
            for basis in range(4):
                expected=basis ^ (((basis>>targets[0])&1)<<targets[1])
                np.testing.assert_array_equal(u@np.eye(4)[:,basis],np.eye(4)[:,expected])
        np.testing.assert_array_equal(r.embed_native(r.X,[0])@np.eye(4)[:,0],np.eye(4)[:,1])
        np.testing.assert_array_equal(r.embed_native(r.X,[1])@np.eye(4)[:,0],np.eye(4)[:,2])

    def test_nonunital_reset_mixture_channel_and_local_embedding(self):
        error={'type':'qerror','gate_qubits':[[0]],'probabilities':[.7,.3],
               'instructions':[[{'name':'id','qubits':[0]}],[{'name':'reset','qubits':[0]}]]}
        channel=r.reconstruct_superop(error)
        bell=np.array([1,0,0,1])/np.sqrt(2);rho=np.outer(bell,bell)
        for physical in (0,1):
            # Reset destroys entanglement and replaces the selected qubit by |0>.
            reset=np.diag([.5,.5,0,0]) if physical==1 else np.diag([.5,0,.5,0])
            np.testing.assert_allclose(r.apply_local_superop(rho,channel,[physical]),.7*rho+.3*reset,atol=2e-16,rtol=0)

    def test_serialized_pauli_string_and_noncommuting_sequence_order(self):
        rho=np.zeros((4,4),complex);rho[0,0]=1
        out=r.noise_instruction(rho,{'name':'pauli','qubits':[0,1],'params':['XI']},2)
        np.testing.assert_array_equal(out,np.diag([0,0,1,0]))
        with self.assertRaisesRegex(ValueError,'Unsupported'):r.noise_instruction(rho,{'name':'kraus','qubits':[0]},2)

    def test_qasm_safe_parser_and_idle_wire_rejection(self):
        text='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[5];\nrz(-pi/2) q[0];\nsx q[1];\ncx q[1],q[0];'
        operations=r.parse_native_qasm(text);self.assertEqual(operations[0],('rz',(0,),-np.pi/2))
        for changed in (text.replace('sx q[1]','sx q[2]'),text.replace('q[5]','q[2]'),text.replace('-pi/2','__import__("os")')):
            with self.assertRaises(ValueError):r.parse_native_qasm(changed)
        self.assertAlmostEqual(np.trace(r.native_density(operations)).real,1.)

if __name__=='__main__':unittest.main()
