from __future__ import annotations
import logging
import json
from jsonschema import validate, ValidationError
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import PreTrainedModel, PreTrainedTokenizer
from itertools import chain
from collections import defaultdict

from schemaformer.json import *


class Schemaformer:
    def __init__(
        self, model, tokenizer, temperature: float = 1.0
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.vocab = tokenizer.get_vocab()
        self.inv_vocab = {v: k for k, v in self.vocab.items()}
        self.vocab_by_start_char = defaultdict(list)
        for k, v in self.vocab.items():
            if k.startswith('Ġ'):
                k = " " + k[1:]
            if len(k) > 0:
                self.vocab_by_start_char[k[0]].append((k, v))
        
        self.vocab_by_first_2_chars = defaultdict(list)
        for k, v in self.vocab.items():
            if k.startswith('Ġ'):
                k = " " + k[1:]
            if len(k) > 0:
                self.vocab_by_first_2_chars[k[:2]].append((k, v))

        self.temperature = temperature

    def get_prefix_allowed_tokens_fn(self, prompt, schema):
        prompt_len = len(self.tokenizer.encode(prompt))
        def prefix_allowed_tokens_fn(batch_id, input_ids):
            # Check if it is a valid JSON string prefix for the given schema
            
            # Convert the input_ids to a string
            input_str = self.tokenizer.decode(input_ids[prompt_len:])

            # Validate the prefix
            valid_start_chars = set()
            maybe_valid = []
            for k, v in self.vocab_by_start_char.items():
                if json_validate_prefix(f"{input_str}{k}", schema):
                    valid_start_chars.add(k)
                    maybe_valid.append(v)

            maybe_valid_2 = []
            for k, v in self.vocab_by_first_2_chars.items():
                if k[0] in valid_start_chars:
                    if json_validate_prefix(f"{input_str}{k}", schema):
                        maybe_valid_2.append(v)
                
            valid = []
            for k, v in chain(*maybe_valid_2):
                if json_validate_prefix(f"{input_str}{k}", schema):
                    valid.append(v)

            eos = self.tokenizer.eos_token_id
            try:
                validate(json.loads(input_str), schema)
                valid = [eos]
            except:
                valid = [e for e in valid if e != eos]
            
            # if len(valid) == 0:
            #     print(f"{input_str=} {len(valid)=}")
            #     print(f"json_validate_prefix(input_str, schema)")
            #     import code; code.interact(local=dict(globals(), **locals()))
            return valid

        return prefix_allowed_tokens_fn

    def __call__(self, prompt, schema, max_tokens=100):
        preamble = f"\nAnswer according to the schema: {json.dumps(schema)}:"
        prompt += preamble
        tokenized_prompt = self.tokenizer.encode(prompt, return_tensors="pt")
        response = self.model.generate(
            tokenized_prompt,
            max_new_tokens=max_tokens,
            num_return_sequences=1,
            prefix_allowed_tokens_fn=self.get_prefix_allowed_tokens_fn(prompt, schema),
            temperature=self.temperature,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        text = self.tokenizer.decode(response[0][tokenized_prompt.size(1):-1])
        return json.loads(text)