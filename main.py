import json
import argparse
import os

from transformers import AutoModelForCausalLM, AutoTokenizer
from schemaformer.schemaformer import Schemaformer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="databricks/dolly-v2-3b")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--prompt", type=str, default="")
    parser.add_argument("--schema_filename", type=str, default="schema.json")

    args = parser.parse_args()

    # Define the JSON schema
    with open(args.schema_filename, "r") as f:
        schema = json.load(f)
    
    print("Loading model and tokenizer...")
    model = AutoModelForCausalLM.from_pretrained(args.model, use_cache=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True, use_cache=True)
    print("Loaded model and tokenizer")
    prompt = f"Tell me a 4 word story in this schema: {schema}"

    schema_model = Schemaformer(model, tokenizer, temperature=args.temperature)
    print("Generating...")
    res = schema_model(args.prompt, schema)
    print("Generated: ", res)

if __name__ == "__main__":
    main()
