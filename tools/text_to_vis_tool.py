
import re

import pandas as pd

from functions.gptconfig import MODEL_4O, MODEL_35_TURBO, MODEL_O3_MINI
from functions.langchain_utils import get_llm, convert_chat_models_to_langchain
from prompt_visualization_builder.IPromptVisualizationBuilder import IPromptVisualizationBuilder
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()
class TextToVis:
    def __init__(self, llm, prompt_builder:IPromptVisualizationBuilder, model_type: str):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.model_type = model_type
        self.all_suported_models = [MODEL_35_TURBO, MODEL_4O, MODEL_O3_MINI]
         
    def generate_visualization(self, question: str, df_dataset: pd.DataFrame, df_name: str, debug=False, **kwargs):
        
        if self.model_type in  self.all_suported_models:
            
            prompt_model_info = self.prompt_builder.build_prompt(question, df_dataset, df_name, self.model_type, **kwargs)
        
            task = '''
            Generate Python Code Script.
            The script should only include code, no comments.
            '''
            
            messages=[
                {"role": "system", "content": task}, 
                {"role": "user","content": prompt_model_info["prompt"]}
            ]
            
            messages = convert_chat_models_to_langchain(messages, self.model_type)
            
            response = self.llm.invoke(messages, config={"callbacks": [langfuse_handler]})        
            result = {
                "question": question,
                "model_type": self.model_type,
                "prompt_model": prompt_model_info,
                "llm_response": response.content,
                "visualization_code": self.__get_response(response.content),
            }
            
            self.__show_debug(response, debug=debug)
            
            return result
        else:
            raise ValueError(f"Model type {self.model_type} is not supported.")

        
    def __get_response(self, llm_response):
        match = re.search(r'```python\n(.*?)\n```', llm_response, re.DOTALL)
        if match:
            python_code = match.group(1)
            return python_code
        else:
            if self.model_type in [MODEL_35_TURBO, MODEL_O3_MINI]:
                return llm_response
            else:
                print("Bloco de código Python não encontrado.")
                return ""
                            
    def __show_debug(self, data, debug=False):
        if debug:
            print("Debugging information:")
            print(data)
            # import streamlit as st
            # st.write(data)
            
class VisToolInput(BaseModel):
    question: str = Field(description="The natural language query")
    rows: list[dict] = Field(description="The rows (database result)")


class VisTool(BaseTool):
    name: str = "text_to_vis"
    description: str = (
        "Generate python code from natural language query and database result(df) and return a visualization (charts)."
    )
    args_schema: type[BaseModel] = VisToolInput
    text_to_vis: TextToVis = None

    def _run(self, question: str, df: pd.DataFrame) -> dict:
        """
        Generate python code from natural language query and database result (df). The code is executed and generate an image containing a visualization that represents a chart about data.

        Args:
            question: The text string that represents the user question.
            df: The database results used to generate a visualization related tue user question

        Returns:
            The dict containing python code, figure and other metadatas.
        """
   
        tool_result = self.text_to_vis.generate_visualization(
            question, df, "df", debug=False
        )
        code = self.text_to_vis.prompt_builder.plot(tool_result)
        
        namespace = {"df": df, "pd": pd, "code_generated": code}
        try:
            exec(code, namespace)
        except Exception as e:
            print(f"Error executing code: {e}")
            namespace["error"] = str(e)    
        
        return namespace
