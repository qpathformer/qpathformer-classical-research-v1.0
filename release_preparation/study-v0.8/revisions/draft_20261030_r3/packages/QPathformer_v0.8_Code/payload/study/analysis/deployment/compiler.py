"""Exact D2 linear-Pauli-logit conversion, to float64 rounding precision.

The 25 period-two Fourier construction nodes force each bank independently.
They are not training data, are never routed, and fit no labels. Two RY(pi*x)
occurrences per coordinate imply Fourier support {-2,-1,0,1,2} in each input.
Only the approved Multi D2 core and linear logit head are supported.
This creates another representation of an existing checkpoint, not a new arm.
"""
from __future__ import annotations
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'quantum'))
import circuits
from models import sigmoid, trig_features

METHODS=('qmulti_kmeans','qmulti_hash')
BASIS=('1','cos(pi*x)','sin(pi*x)','cos(2*pi*x)','sin(2*pi*x)')
NODES=-1.+2.*np.arange(5,dtype=np.float64)/5.
GRID=np.stack(np.meshgrid(NODES,NODES,indexing='ij'),axis=-1).reshape(25,2)
NORMS=np.array([1.,.5,.5,.5,.5])


def real_basis(x):
    x=np.asarray(x,dtype=np.float64)
    return np.stack((np.ones_like(x),np.cos(np.pi*x),np.sin(np.pi*x),
                     np.cos(2*np.pi*x),np.sin(2*np.pi*x)),axis=-1)


def compile_bank(core,head,moment_count,return_evidence=False):
    core=np.asarray(core,dtype=np.float64);head=np.asarray(head,dtype=np.float64)
    if (core.shape!=(2,2,2) or moment_count not in (1,5)
            or head.shape!=(moment_count+1,) or not np.isfinite(core).all()
            or not np.isfinite(head).all()):
        raise ValueError('Only finite D2 core[2,2,2] with one/five moments and linear head is supported')
    moments=circuits.moments(GRID,core,moment_count)
    logits=moments@head[:-1]+head[-1]
    basis=real_basis(NODES)
    # Exact discrete orthogonal projection for the registered Fourier support.
    # Analytic basis norms are used; no inverse, least squares, or regression.
    coefficients=((basis.T@logits.reshape(5,5)@basis)/25.)/NORMS[:,None]/NORMS[None,:]
    coefficients=coefficients.reshape(25)
    if not np.isfinite(coefficients).all():raise ValueError('Nonfinite converted coefficients')
    if not return_evidence:return coefficients
    return coefficients,{'grid':GRID.copy(),'grid_moments':moments,'grid_logits':logits,
        'basis_norms':NORMS.copy(),'forced_bank':True,'construction_statevector_examples':25,
        'construction_layer_applications':50,'construction_feature_ry_gates':100,
        'construction_trainable_ry_gates':100,'construction_trainable_rz_gates':100,
        'construction_cx_gates':50,'construction_moment_values':25*moment_count,
        'coefficient_order':'row-major tensor basis of x0 then x1; '+repr(BASIS)}


def compile_model(method,parameters,return_evidence=False):
    if method not in METHODS:raise ValueError('Conversion only accepts approved Multi routed models')
    count=5;width=14
    parameters=np.asarray(parameters,dtype=np.float64)
    if parameters.shape!=(5*width,) or not np.isfinite(parameters).all():
        raise ValueError('Incorrect checkpoint parameter shape or values')
    output=[];evidence=[]
    for bank in range(5):
        theta=parameters[bank*width:(bank+1)*width]
        coefficients,record=compile_bank(theta[:8].reshape(2,2,2),theta[8:],count,True)
        record['bank']=bank;output.append(coefficients);evidence.append(record)
    return (np.asarray(output),evidence) if return_evidence else np.asarray(output)


def predict_coefficients(x,coefficients,route=None):
    """One shared raw-feature kernel for compiled and learned Trig25 tables.

    One global bank or five routed banks are accepted. This function performs
    no coefficient fitting and does not infer a route from checkpoint contents.
    """
    x=np.asarray(x,dtype=np.float64);coefficients=np.asarray(coefficients,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():raise ValueError('Finite N-by-2 inputs required')
    if coefficients.shape not in ((1,25),(5,25),(1,121)) or not np.isfinite(coefficients).all():raise ValueError('Finite registered coefficient table required')
    if len(coefficients)==1:
        if route is not None:raise ValueError('Global coefficient kernel does not accept routes')
        r=np.zeros(len(x),dtype=np.int64)
    else:
        r=np.asarray(route)
        if r.shape!=(len(x),) or not np.isfinite(r).all() or np.any(r!=r.astype(np.int64)) or np.any(r<0) or np.any(r>=5):
            raise ValueError('Integer routes0..4 required')
    # Feature construction is shared once per input. Router execution is external
    # and must be included by any raw-input latency benchmark.
    phi=trig_features(x,5 if coefficients.shape[1]==121 else 2)
    z=np.einsum('ni,ni->n',phi,coefficients[r.astype(np.int64)])
    return sigmoid(z),z


def predict_compiled(x,coefficients,route):
    if np.asarray(coefficients).shape!=(5,25):raise ValueError('Compiled circuit table must have five banks')
    return predict_coefficients(x,coefficients,route)


def learned_trig_coefficients(method,parameters):
    """Repack trained Trig25 weights without fitting or changing their values."""
    if method not in ('trig_kmeans','trig_hash','trig121_global'):raise ValueError('Learned registered trigonometric method required')
    banks=1 if method.endswith('_global') else 5;width=121 if method=='trig121_global' else 25
    values=np.asarray(parameters,dtype=np.float64)
    if values.shape!=(banks*width,) or not np.isfinite(values).all():raise ValueError('Wrong learned trigonometric parameter table')
    return values.reshape(banks,width).copy()


def inference_work(n,banks=5):
    if int(n)!=n or n<0:raise ValueError('Nonnegative record count required')
    if banks not in (1,5):raise ValueError('One/five banks required')
    return {'records':int(n),'trig_feature_values':25*int(n),'core_statevector_examples':0,
            'logit_dot_multiplications':25*int(n),'logit_dot_additions':24*int(n),
            'sigmoid_evaluations':int(n),'coefficient_bytes':banks*25*8,
            'scope':'Analytical arithmetic convention; not measured FLOPs. Router and feature trigonometric operations are separate.'}
