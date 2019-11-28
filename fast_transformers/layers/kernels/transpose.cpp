#include "fast_transformers/layers/kernels/transpose.h"

#include <cstring>

namespace fast_transformers {
namespace layers {
namespace kernels {

static void TransposeForScoreImpl(float* output, const float* input,
                                  int64_t batch_size, int64_t seq_length,
                                  int64_t num_attention_heads, int64_t width) {
#pragma omp parallel for
  for (int64_t idx = 0; idx < batch_size * seq_length; ++idx) {
    int64_t batch_idx = idx / seq_length;
    int64_t seq_idx = idx % seq_length;
    for (int64_t head_idx = 0; head_idx < num_attention_heads; ++head_idx) {
      auto* src = input +
                  batch_idx * (seq_length * num_attention_heads * width) +
                  seq_idx * width + head_idx * seq_length * width;
      auto* dst = output +
                  batch_idx * (seq_length * num_attention_heads * width) +
                  seq_idx * num_attention_heads * width + head_idx * width;
// std::copy(src, src + width, dst);
#pragma omp simd
      for (int64_t width_idx = 0; width_idx < width; ++width_idx) {
        dst[width_idx] = src[width_idx];
      }
    }
  }
}

void TransposeForScore(core::Tensor* output, const core::Tensor& input) {
  TransposeForScoreImpl(output->mutableData<float>(), input.data<float>(),
                        output->shape(0), output->shape(1), input.shape(1),
                        input.shape(3));
}

void SplitAddBiasTransposeForScore(core::Tensor* output_tensor,
                                   const core::Tensor& input_tensor,
                                   const core::Tensor& bias_tensor) {
  auto batch_size = output_tensor->shape(1);
  auto seq_length = output_tensor->shape(3);
  auto weight_num = output_tensor->shape(0);
  auto num_attention_heads = output_tensor->shape(2);
  auto width = output_tensor->shape(4);
  auto input = input_tensor.data<float>();
  auto bias = bias_tensor.data<float>();
  auto output = output_tensor->mutableData<float>();

#pragma omp parallel for
  for (int64_t idx = 0; idx < batch_size * weight_num * seq_length; ++idx) {
    auto batch_idx = idx / (seq_length * weight_num);
    auto seq_idx = idx / weight_num % seq_length;
    auto weight_idx = idx % weight_num;

    for (int64_t head_idx = 0; head_idx < num_attention_heads; ++head_idx) {
      auto* src_ptr =
          input +
          batch_idx * (seq_length * weight_num * num_attention_heads * width) +
          seq_idx * weight_num * num_attention_heads * width +
          weight_idx * (num_attention_heads * width) + head_idx * width;
      auto* dst_ptr =
          output +
          weight_idx * (batch_size * num_attention_heads * seq_length * width) +
          batch_idx * (num_attention_heads * seq_length * width) +
          head_idx * seq_length * width + seq_idx * width;
      auto* bias_ptr =
          bias + weight_idx * width * num_attention_heads + head_idx * width;
#pragma omp simd
      for (int64_t width_idx = 0; width_idx < width; ++width_idx) {
        dst_ptr[width_idx] = src_ptr[width_idx] + bias_ptr[width_idx];
      }
    }
  }  // end for
}

}  // namespace kernels
}  // namespace layers
}  // namespace fast_transformers