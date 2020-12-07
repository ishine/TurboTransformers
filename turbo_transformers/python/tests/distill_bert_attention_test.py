import turbo_transformers

import unittest
import sys
import torch
from transformers.modeling_distilbert import DistilBertConfig
from transformers.modeling_distilbert import MultiHeadSelfAttention as DistilAttention
from torch import nn

import os
sys.path.append(os.path.dirname(__file__))
import test_helper

fname = "tt_distrill_attention.txt"


def create_test(batch_size, seq_length):
    class TestDistillBertAttention(unittest.TestCase):
        def init_data(self, use_cuda):
            test_device = torch.device('cuda:0') if use_cuda else \
                torch.device('cpu:0')
            if not use_cuda:
                torch.set_num_threads(4)
                turbo_transformers.set_num_threads(4)

            torch.set_grad_enabled(False)
            self.cfg = DistilBertConfig(attention_probs_dropout_prob=0.0,
                                        hidden_dropout_prob=0.0)
            self.cfg.output_attentions = True
            self.torch_attention = DistilAttention(self.cfg)
            self.torch_sa_layer_norm = nn.LayerNorm(
                normalized_shape=self.cfg.dim, eps=1e-12)
            self.torch_attention.eval()
            self.torch_sa_layer_norm.eval()
            if use_cuda:
                self.torch_attention.to(test_device)
                self.torch_sa_layer_norm.to(test_device)

            # Get FT Attention
            self.turbo_attention = turbo_transformers.DistillBertAttention.from_torch(
                self.torch_attention, self.torch_sa_layer_norm)

            hidden_size = self.cfg.hidden_size
            self.input_tensor = torch.rand(size=(batch_size, seq_length,
                                                 hidden_size),
                                           dtype=torch.float32,
                                           device=test_device)
            # NOTE, the mask of distilled attention is different from huggingface bert attention.
            self.attention_mask = torch.ones((batch_size, seq_length),
                                             dtype=torch.float32,
                                             device=test_device)

        def check_torch_and_turbo(self, use_cuda, num_iter=1):
            self.init_data(use_cuda)
            device = "GPU" if use_cuda else "CPU"
            torch_model = lambda: self.torch_sa_layer_norm(
                self.torch_attention(query=self.input_tensor,
                                     key=self.input_tensor,
                                     value=self.input_tensor,
                                     mask=self.attention_mask,
                                     output_attentions=False)[0] + self.
                input_tensor)
            torch_attention_result, torch_qps, torch_time_consume = \
                test_helper.run_model(torch_model, use_cuda, num_iter, use_profile=False)
            print(
                f"DistilAttention+LN \"({batch_size},{seq_length:03})\" ",
                f"{device} Torch QPS, {torch_qps}, time, {torch_time_consume}")

            turbo_model = lambda: self.turbo_attention(
                self.input_tensor,
                self.attention_mask,
                output_attentions=self.cfg.output_attentions)[0]

            turbo_attention_result, turbo_qps, turbo_time_consume = \
                test_helper.run_model(turbo_model, use_cuda,
                                      num_iter)
            print(
                f"DistilAttention \"({batch_size},{seq_length:03})\" ",
                f" {device} Turbo QPS, {turbo_qps}, time, {turbo_time_consume}"
            )

            self.assertTrue(
                torch.max(
                    torch.abs(torch_attention_result - turbo_attention_result))
                < (1e-3 if use_cuda else 1e-4))

        def test_distillbert_attention(self):
            self.check_torch_and_turbo(use_cuda=False, num_iter=1)
            if torch.cuda.is_available() and \
                    turbo_transformers.config.is_compiled_with_cuda():
                self.check_torch_and_turbo(use_cuda=True, num_iter=1)

    globals(
    )[f"TestDistillBertAtt{batch_size}_{seq_length:3}"] = TestDistillBertAttention


with open(fname, "w") as fh:
    fh.write(", torch, turbo_transformers\n")
for batch_size in [1, 2]:
    for seq_length in [10, 20, 128]:
        create_test(batch_size, seq_length)

if __name__ == '__main__':
    unittest.main()