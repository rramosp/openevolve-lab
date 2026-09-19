"""
Initial program: A naive linear model for symbolic regression.
This model predicts the output as a linear combination of input variables
or a constant if no input variables are present.
The function is designed for vectorized input (X matrix).

Target output variable: sigma (Stress)
Input variables (columns of x): epsilon (Strain), T (Temperature)
"""
import numpy as np

# Input variable mapping for x (columns of the input matrix):
#   x[:, 0]: epsilon (Strain)
#   x[:, 1]: T (Temperature)

# Parameters will be optimized by BFGS outside this function.
# Number of parameters expected by this model: 10.
# Example initialization: params = np.random.rand(10)

# EVOLVE-BLOCK-START

def func(x, params):
    """
    Calculates the model output using a non-linear polynomial combination 
    of strain (epsilon) and temperature (T) to model stress (sigma).
    Operates on a matrix of samples.

    Args:
        x (np.ndarray): A 2D numpy array of input variable values, shape (n_samples, 2).
                        x[:, 0] is epsilon (Strain)
                        x[:, 1] is T (Temperature)
        params (np.ndarray): A 1D numpy array of parameters.
                             Expected length: 10.

    Returns:
        np.ndarray: A 1D numpy array of predicted output values, shape (n_samples,).
    """
    eps = np.maximum(x[:, 0], 0.0)
    T = x[:, 1]
    sqrt_eps = np.sqrt(eps)
    
    # 10-parameter polynomial model capturing strain hardening, thermal softening,
    # and their interactions. Linear in parameters for stable BFGS optimization.
    result = (
        params[0] +
        params[1] * eps +
        params[2] * sqrt_eps +
        params[3] * T +
        params[4] * eps * T +
        params[5] * sqrt_eps * T +
        params[6] * (eps**2) +
        params[7] * (T**2) +
        params[8] * (eps**2) * T +
        params[9] * eps * (T**2)
    )
    return result
    
# EVOLVE-BLOCK-END

# This part remains fixed (not evolved)
def run_search():
    return func
