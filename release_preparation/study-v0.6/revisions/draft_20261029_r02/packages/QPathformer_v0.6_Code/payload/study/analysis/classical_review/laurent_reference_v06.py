"""Independent D2 circuit-to-Trig25 conversion by Laurent gate propagation.

No producer, interpolation, data, router, checkpoint or model imports. The input
contract is exactly two RY(pi*x[q]) encodings per coordinate, with constant RY/RZ
gates and CX(q0,q1) after each layer. Float64 coefficients approximate an exact
algebraic identity; neither bitwise parity nor equality at rounded thresholds is
assumed. Observable order is X0,X1,Z0,Z1,Z0Z1 in logical |q0 q1>.
"""
import math
import numpy as np

I = np.eye(2, dtype=np.complex128)
X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
Z = np.diag([1., -1.]).astype(np.complex128)
CX = np.array([[1,0,0,0], [0,1,0,0], [0,0,0,1], [0,0,1,0]], dtype=np.complex128)
PAULI = np.array([np.kron(X,I),np.kron(I,X),np.kron(Z,I),np.kron(I,Z),np.kron(Z,Z)])
BASIS = ('1', 'cos(pi*x)', 'sin(pi*x)', 'cos(2*pi*x)', 'sin(2*pi*x)')


def checked_core(core):
    a = np.asarray(core, dtype=np.float64)
    if a.shape != (2,2,2) or not np.isfinite(a).all():
        raise ValueError('Exactly two finite layers [2,2,2] required')
    return a


def _rotation(angle, axis):
    # exp(-i*angle*sigma/2), independent of the producer's pairwise update.
    sigma = Y if axis == 0 else Z
    return math.cos(float(angle)/2)*I - 1j*math.sin(float(angle)/2)*sigma


def _local(matrix, qubit):
    return np.kron(matrix,I) if qubit == 0 else np.kron(I,matrix)


def amplitude_coefficients(core):
    """Return amplitudes keyed by INTEGER frequencies of t_q=pi*x_q.

    Intermediate keys count half-angle exponents; the two encodings ensure even
    keys at the end. Each final amplitude has frequencies -1,0,1 per coordinate.
    """
    core = checked_core(core)
    terms = {(0,0): np.array([1,0,0,0], dtype=np.complex128)}
    for layer in range(2):
        for qubit in (0,1):
            changed = {}
            for exponent, amplitude in terms.items():
                # RY(t) = exp(+it/2)*(I-Y)/2 + exp(-it/2)*(I+Y)/2.
                for sign in (-1,1):
                    key = list(exponent); key[qubit] += sign; key = tuple(key)
                    part = _local((I-sign*Y)/2, qubit) @ amplitude
                    changed[key] = changed.get(key, np.zeros(4, complex)) + part
            gate = _local(_rotation(core[layer,qubit,1],1) @ _rotation(core[layer,qubit,0],0),qubit)
            terms = {key: gate @ amplitude for key, amplitude in changed.items()}
        terms = {key: CX @ amplitude for key, amplitude in terms.items()}
    if any(a % 2 or b % 2 or abs(a)>2 or abs(b)>2 for a,b in terms):
        raise RuntimeError('Unexpected half-angle support; do not claim Trig25 containment')
    return {(a//2,b//2): amplitude for (a,b), amplitude in terms.items()}


def observable_fourier_coefficients(core):
    """Return [5,5,5] coefficients in complex frequencies [-2,-1,0,1,2]."""
    terms = amplitude_coefficients(core)
    result = np.zeros((5,5,5), dtype=np.complex128)
    for left_frequency, left in terms.items():
        for right_frequency, right in terms.items():
            frequency = tuple(b-a for a,b in zip(left_frequency,right_frequency))
            if any(abs(k)>2 for k in frequency):
                raise RuntimeError('Observable frequency support exceeded degree two')
            for observable, matrix in enumerate(PAULI):
                result[observable,frequency[0]+2,frequency[1]+2] += np.vdot(left,matrix @ right)
    return result


def _real_transform():
    # c_cos(k)=a_(+k)+a_(-k); c_sin(k)=i*(a_(+k)-a_(-k)).
    transform = np.zeros((5,5), dtype=np.complex128)
    transform[0,2] = 1
    transform[1,1] = transform[1,3] = 1
    transform[2,1],transform[2,3] = -1j,1j
    transform[3,0] = transform[3,4] = 1
    transform[4,0],transform[4,4] = -1j,1j
    return transform


def observable_trig_coefficients(core):
    """Return [5 observables,25 row-major real basis coefficients], diagnostics."""
    fourier = observable_fourier_coefficients(core)
    transform = _real_transform()
    converted = np.array([transform @ matrix @ transform.T for matrix in fourier])
    conjugacy = float(np.max(np.abs(fourier-fourier[:,::-1,::-1].conj())))
    imaginary = float(np.max(np.abs(converted.imag)))
    scale = max(1.,float(np.max(np.abs(converted))))
    if imaginary > 128*np.finfo(float).eps*scale or conjugacy > 128*np.finfo(float).eps*scale:
        raise RuntimeError('Failed real-observable conjugacy check')
    return converted.real.reshape(5,25), {
        'maximum_conjugacy_residual': conjugacy,
        'maximum_real_basis_imaginary_residual': imaginary,
        'state_frequency_support': [-1,0,1],
        'observable_frequency_support': [-2,-1,0,1,2],
        'basis_order': list(BASIS),
        'construction': 'gate-level Laurent propagation; no sampled inputs or linear solve',
    }


def compile_bank(core, head, moment_count=5, return_diagnostics=False):
    if moment_count not in (1,5): raise ValueError('Only scalar or five-Pauli linear heads supported')
    head = np.asarray(head,dtype=np.float64)
    if head.shape != (moment_count+1,) or not np.isfinite(head).all():
        raise ValueError('Finite linear head weights and bias required')
    moments, diagnostics = observable_trig_coefficients(core)
    coefficients = head[:-1] @ moments[:moment_count]
    coefficients[0] += head[-1]
    if not np.isfinite(coefficients).all(): raise ValueError('Nonfinite converted coefficients')
    return (coefficients, diagnostics) if return_diagnostics else coefficients


def compile_model(method, parameters, return_diagnostics=False):
    if method not in ('qscalar_kmeans','qmulti_kmeans'):
        raise ValueError('Compiler supports only registered Scalar/Multi checkpoints')
    count = 1 if method == 'qscalar_kmeans' else 5
    theta = np.asarray(parameters,dtype=np.float64)
    width = 8+count+1
    if theta.shape != (5*width,) or not np.isfinite(theta).all():
        raise ValueError('Exact five-bank checkpoint packing required')
    coefficients=[];diagnostics=[]
    for row in theta.reshape(5,width):
        value, check = compile_bank(row[:8].reshape(2,2,2),row[8:],count,True)
        coefficients.append(value); diagnostics.append(check)
    result=np.asarray(coefficients)
    return (result, diagnostics) if return_diagnostics else result


def features(x):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():
        raise ValueError('Finite N-by-2 inputs required')
    result=[]
    for row in x:
        local=[[1.,math.cos(math.pi*v),math.sin(math.pi*v),math.cos(2*math.pi*v),math.sin(2*math.pi*v)] for v in row]
        result.append([a*b for a in local[0] for b in local[1]])
    return np.asarray(result,dtype=np.float64).reshape(len(x),25)


def predict_compiled(x, coefficients, route):
    phi=features(x);coefficients=np.asarray(coefficients,dtype=np.float64);route=np.asarray(route)
    if coefficients.shape!=(5,25) or not np.isfinite(coefficients).all():
        raise ValueError('Finite five-bank Trig25 coefficients required')
    if route.shape!=(len(phi),) or route.dtype.kind not in 'iu' or np.any(route<0) or np.any(route>4):
        raise ValueError('Exact integer bank identities0..4 required')
    logits=np.asarray([math.fsum(float(a)*float(b) for a,b in zip(row,coefficients[bank])) for row,bank in zip(phi,route)])
    probability=np.exp(-np.logaddexp(0.,-logits))
    return probability,logits
