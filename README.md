## schemaformer
Schemaformer is a Python library that leverages the power of Hugging Face Transformers to generate text that follows a specified JSON schema. With Schemaformer, you can easily create coherent and structured text based on a well-defined schema, ensuring consistency and adherence to predefined rules. Importantly it ensures deterministically that the output either is valid for the schema or exausted the max tokens and is a valid prefix for the schema.

# Features
Utilizes state-of-the-art transformer models from the Hugging Face library
Validates generated text against a user-defined JSON schema
Customizable generation parameters for fine-tuning the output

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from schemaformer.schemaformer import Schemaformer

modelname = "databricks/dolly-v2-3b"
model = AutoModelForCausalLM.from_pretrained(modelname, use_cache=True)
tokenizer = AutoTokenizer.from_pretrained(modelname, use_fast=True, use_cache=True)
schemaformer = Schemaformer(model, tokenizer)
```

Define your JSON schema and generate text based on the schema:
```
schema = {
    "type": "object",
    "properties": {
        "story": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "pattern": "^once upon a time"
                }
            },
            "required": ["title"]
        }
    },
    "required": ["story"]
}
prompt = "Tell me a 4 word story"
generated_text = schemaformer(prompt, schema)

print(generated_text)
# {"story":{"title":"once upon a time"}}
```
# Work in Progress

Please note that Schemaformer is a work in progress. While the core functionality is in place, much is broken owing to the hastly implemented valid pre-fix checking. We appreciate your understanding and welcome any feedback, contributions, or bug reports to help us improve the library.

# Customization
Schemaformer allows you to customize the generation process by modifying parameters such as the temperature, max tokens, and more:

```
generated_text = schemaformer.generate_text(
    prompt,
    schema,
    temperature=0.8,
    max_tokens=100
)
```

# Contributing
We welcome contributions to Schemaformer! If you'd like to help improve the library or report any issues, please feel free to open a pull request or submit an issue on the GitHub repository.

# License
Schemaformer is released under the MIT License. See LICENSE for more information.