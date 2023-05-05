from __future__ import annotations
import logging
import json
from multiprocessing import Pool
from jsonschema import validate, ValidationError
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import PreTrainedModel, PreTrainedTokenizer
from itertools import chain, count
from collections import defaultdict

from schemaformer.json import *


def group_vocab_by_chars(vocab, num_chars):
    vocab_by_chars = set()
    for k, v in vocab.items():
        if k.startswith('Ġ'):
            k = " " + k[1:]
        if len(k) >= num_chars:
            vocab_by_chars.add(k[:num_chars])
    return vocab_by_chars

def get_valids(arg):
    prefix, input_str, vocab, valid_prefixes, schema = arg
    valid_list = []
    new_valid_prefixes_l = set()
    prev_prefix = prefix[:-1]
    if len(prev_prefix) > 0 and prev_prefix not in valid_prefixes:
        return (new_valid_prefixes_l, valid_list)

    if json_validate_prefix(f"{input_str}{prefix}", schema):    
        new_valid_prefixes_l.add(prefix)
        if prefix in vocab:
            valid_list.append(vocab[prefix])
    
    return (new_valid_prefixes_l, valid_list)

class Schemaformer:
    def __init__(
        self, model, tokenizer, temperature: float = 1.0
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.vocab = tokenizer.get_vocab()
        self.vocab_with_substutution = {' ' + k[1:] if k.startswith('Ġ') else k: v for k, v in self.vocab.items() }
        self.inv_vocab = {v: k for k, v in self.vocab.items()}
        self.temperature = temperature
                
        self.vocab_by_chars = {}
        for i in count(1):
            self.vocab_by_chars[i] = group_vocab_by_chars(self.vocab, i)
            if len(self.vocab_by_chars[i]) == 0:
                break

    def get_prefix_allowed_tokens_fn(self, prompt, schema):
        prompt_len = len(self.tokenizer.encode(prompt))
        def prefix_allowed_tokens_fn(batch_id, input_ids):
            # Check if it is a valid JSON string prefix for the given schema
            
            # Convert the input_ids to a string
            input_str = self.tokenizer.decode(input_ids[prompt_len:])

            # Validate the prefix
            valid_prefixes = set()
            valid = []
            for n, vocab_by_n_chars in self.vocab_by_chars.items():
                e = tuple(zip(*map(get_valids, [(e, input_str, self.vocab_with_substutution, valid_prefixes, schema) for e in vocab_by_n_chars])))
                if len(e) == 0:
                    break
                new_valid_prefixes_l, valid_lists = e

                valid_prefixes = valid_prefixes.union(*new_valid_prefixes_l)
                valid.extend(chain(*valid_lists))

                if len(valid_prefixes) == 0:
                    break

            eos = self.tokenizer.eos_token_id
            try:
                validate(json.loads(input_str), schema)
                valid = [eos]
            except:
                valid = [e for e in valid if e != eos]
            
            if len(valid) == 0 or len(input_str) == 10:
                print(f"{input_str=} {len(valid)=}")
                print(f"json_validate_prefix(input_str, schema)")
            import code; code.interact(local=dict(globals(), **locals()))
            return valid

        return prefix_allowed_tokens_fn

    def __call__(self, prompt, schema, max_tokens=100, return_response=False):
        preamble = f"\nBased on the previous context produce a json object according to the schema: {json.dumps(schema)}:\n"
        prompt += preamble
        tokenized_prompt = self.tokenizer.encode(prompt, return_tensors="pt")
        tokenized_prompt = tokenized_prompt.to(self.model.device)
        response = self.model.generate(
            tokenized_prompt,
            max_new_tokens=max_tokens,
            num_return_sequences=1,
            prefix_allowed_tokens_fn=self.get_prefix_allowed_tokens_fn(prompt, schema),
            temperature=self.temperature,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        text = self.tokenizer.decode(response[0][tokenized_prompt.size(1):-1])
        if return_response:
            return response, text
        return text