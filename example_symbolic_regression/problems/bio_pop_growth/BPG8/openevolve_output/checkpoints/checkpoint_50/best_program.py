"""
Initial program: A naive linear model for symbolic regression.
This model predicts the output as a linear combination of input variables
or a constant if no input variables are present.
The function is designed for vectorized input (X matrix).

Target output variable: dP_dt (Population growth rate)
Input variables (columns of x): t (Time), P (Population at time t)
"""
import numpy as np

# Input variable mapping for x (columns of the input matrix):
#   x[:, 0]: t (Time)
#   x[:, 1]: P (Population at time t)

# Parameters will be optimized by BFGS outside this function.
# Number of parameters expected by this model: 10.
# Example initialization: params = np.random.rand(10)

# EVOLVE-BLOCK-START

def func(x, params):
    """
    Models population growth rate dP_dt using a non-autonomous logistic-type model.
    Inputs:
        x[:, 0]: t (Time)
        x[:, 1]: P (Population)
    """
    t, P = x[:, 0], x[:, 1]
    # Combines linear, quadratic (logistic), and time-interaction terms
    return params[0]*P + params[1]*(P**2) + params[2]*t*P + params[3]*t + params[4]
    
# EVOLVE-BLOCK-END

# This part remains fixed (not evolved)
def run_search():
    return func
