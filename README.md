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
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["name", "age", "city"]
}
prompt = "I am Alex I am 24 years old and I live in Pittsburgh"
generated_text = schemaformer(prompt, schema)

print(generated_text)
# {'name': 'Alex', 'age': 24, 'city': 'Pittsburgh'}
```

You can also use the pattern functionality to constrain the output e.g.:
```
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^al"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["name", "age", "city"]
}
prompt = "I am Alex I am 24 years old and I live in Pittsburgh"
generated_text = schemaformer(prompt, schema)

print(generated_text)
# {'name': 'al', 'age': 24, 'city': 'Pittsburgh'}
```
# Work in Progress

Please note that Schemaformer is a work in progress. While the core functionality is in place, much is broken owing to the hastly implemented valid pre-fix checking. We appreciate your understanding and welcome any feedback, contributions, or bug reports to help us improve the library.

# Improvements

There are several areas where Schemaformer can be improved:

Caching portions of the string that have already been validated: As Schemaformer processes the input string, it can benefit from caching portions of the string that have already been validated. This will help avoid redundant checks and speed up the validation process.

More efficiently checking tokens per character: Schemaformer currently checks tokens for each character in the input string. Optimizing the token checking process to better handle large input strings can improve the performance of the application.

Improving support for more JSON Schema features: While Schemaformer currently supports a limited set of JSON Schema features, expanding its support for additional features would make it more versatile and useful in various applications. This may include handling more complex schema structures, supporting additional validation keywords, and implementing features like conditional validation.

Speeding up + paralellizing the valid pre-fix checking.


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