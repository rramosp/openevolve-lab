# OpenEvolve Lab

![prompt optimization](imgs/promptopt.png)


## 1. Install

Have your API_KEY of your favourite LLM ready. You can get one for free for small usage from https://openrouter.ai/. I recommend the "Openrouter Free" model which is a wrapper around multiple free models.

   
Check your API key works. For example, if using openrouter.ai:

    > export OPENAI_COMPATIBLE_API_KEY=## YOUR OPENAI COMPATIBLE KEY (openrouter, chatgpt, gemini, etc.) 
    > export OPENAI_COMPATIBLE_URL="https://openrouter.ai/api/v1" ## or chatgpt, gemini, etc.
    > export MODEL="openrouter/free"
    > python call_model.py "what is the meaning of life"

or, if you are using GEMINI

    > export OPENAI_COMPATIBLE_API_KEY=##YOUR GEMINI API KEY##
    > export OPENAI_COMPATIBLE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
    > export MODEL="gemini-3.5-flash"
    > python call_model.py "what is the meaning of life"


Clone open evolve:

    > git clone https://github.com/algorithmicsuperintelligence/openevolve.git

Set `primary_model`, `secondary_model` and `api_base` in `openevolve/examples/function_minimization/config.yaml` to `"openevolve/free"` and `"https://openrouter.ai/api/v1"` or whatever model you are using.

Make a short run of one the examples, `openevolve` reads `$OPENAI_COMPATIBLE_API_KEY`  

    > cd openevolve    
    > export OPENAI_API_KEY=${OPENAI_COMPATIBLE_API_KEY}
    > python openevolve-run.py examples/function_minimization/initial_program.py\
             examples/function_minimization/evaluator.py   \
             --config examples/function_minimization/config.yaml   \
             --iterations 5

Inspect the the output folder

    > ls -R examples/function_minimization/openevolve_output/

Launch the results visualizer

    > python -m openevolve.web.app
    > python scripts/visualizer.py


## 2. Understand `openevolve`

Open your favourite code assistant on this folder and interrogate it about `openevolve`.

You can make, for instance, the following questions:

- _inspect the code under `openevolve` and give me an overview of how openevolve works._
- _explain in detail what are the steps of one iteration._
- _when openevolve starts it only has my initial program how does it initialize the islands?_
- _how does it make sure that child programs in different islands are diverse?_
- _explain in detail how mutation of code happens._
- _give me an example of a full mutation prompt._
- _explain the difference between the primary and secondary models in an openevolve configuration._

[Here](conversation.md) is the conversation I had with Antigravity/Jetski using Google Gemini.

**NOTE**: You can ask your assistant to keep a log of your conversation before you start, for instance by asking it "_from now on, save everything each turn of this conversation in a file named conversation.md including the questions that I will make and the answers that you will give me_"

## 3. Understand the sample run

In `openevolve/examples/function_minimization/`.  

**First** understand what you would need to setup **before** running `openevolve`. This is the initial program `initial_program.py`, the config file `config.yaml`,  and the evaluation function `evaluator.py`. 

**Then**, undestand the output of `openevolve`. Take a look `openevolve_output/` and understand the structure of the output folders and files.

You can use `jq` to pretty print any `json` file. For instance,

    > jq . metadata.json
    > jq . best_program_info.json

Or you can **ask your code assistant** to summarize the results with the following prompts:

- _based on `openevolve/examples/function_minimization/openevolve_output/` please summarize the results of the run._
- _how many tokens were used in each iteration?_

OpenEvolve does not log token count, so you might get a wild guess on this last question. Inspect on whether your coding assistant identifies this fact and how it deals with it. See how Antigravity/Jetski dealt with it in [my conversation](conversation.md)

## 4. Modify `openevolve` to log token count

Observe that `openevolve` doesn't log token count. Modify `openevolve` to log token count, including the number of tokens for each LLM call. 

You might use your code assistant for this. For instance, ask it:

- _modify openevolve so that it logs the token used in each LLM call._

And run again `openevolve` maybe with more iterations now

    > python openevolve-run.py examples/function_minimization/initial_program.py\
             examples/function_minimization/evaluator.py   \
             --config examples/function_minimization/config.yaml   \
             --iterations 10

And ask again your coding assistant

- _summarize the results of the run and include a token analysis count so that I can estimate a cost per iteration._

## 5. Run and inspect an example of your interest.

For instance, under `openevolve/examples/symbolic_regression/` you can find an implementation of **symbolic regression** (finding a formula that fits some data points) for different physics, chemistry and biology datasets.

Follow the instructions there, select a problem to evolve and use the notebook `inspect_symbolic_regression.ipynb` to understand the process and visualize the results. You will probably need to:

- install a few libraries (`h5py`, `scipy`, etc.)
- have a HuggingFace account and log in locally `hf auth login`
- accept in HuggingFace the terms and conditions of use for dataset `nnheui/llm-srbench`

_Suggestion_: Use problems `matsci/MatSci18` or `bio_pop_growth/BPG8` which are the ones showing poorer performance of the initial program. Don't forget to modify each problem `config.yaml` to suit the models you want, or, alternatively, set the `primary_model`, `secondary_model` and `api_base`  in `openevolve/examples/symbolic_regression/data_api.py` before generating the problem folders.

_Suggestion_: Use this script to run openevolve

    export OPENEVOLVE_CONFIG_BASEDIR=examples/symbolic_regression/problems/matsci/MatSci18
    python openevolve-run.py ${OPENEVOLVE_CONFIG_BASEDIR}/initial_program.py \
                             ${OPENEVOLVE_CONFIG_BASEDIR}/evaluator.py \
                             --config ${OPENEVOLVE_CONFIG_BASEDIR}/config.yaml \
                             --iterations 10

Use your coding assistant to debug any issues you might face. For instance, I encountered that with `MatSci18` the solution was not actually evolving stalling at a very large negative score. See again,  [my conversation](conversation.md) to see how I addressed this.
