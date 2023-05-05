import json
import time
import argparse
import os
import code
import torch

from transformers import AutoModelForCausalLM, AutoTokenizer
from schemaformer.schemaformer import Schemaformer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="databricks/dolly-v2-3b")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--prompt", type=str, default="I am Alex I am 24 years old and I live in Pittsburgh")
    parser.add_argument("--schema_filename", type=str, default="data/schema0.json")
    parser.add_argument("--cuda", action="store_true")
    args = parser.parse_args()

    # Define the JSON schema
    with open(args.schema_filename, "r") as f:
        schema = json.load(f)
    
    print("Loading model and tokenizer...")
    model = AutoModelForCausalLM.from_pretrained(args.model, use_cache=True)
    if args.cuda:
        model.cuda()
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True, use_cache=True)
    print("Loaded model and tokenizer")

    schema_model = Schemaformer(model, tokenizer, temperature=args.temperature)
    print("Generating...")
    s = time.time()
    tokens, res = schema_model(args.prompt, schema, return_response=True)
    print("Took: ", time.time() - s)
    print("Generated: ", res)
    code.interact(local=dict(globals(), **locals()))
    decoded_tokens = [tokenizer.decode(e) for e in tokens]

if __name__ == "__main__":
    main()
