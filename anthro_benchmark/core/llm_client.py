# Copyright 2025 The Anthropomorphism Benchmark Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LLM client initialization and management for dialogue generation.
"""

import dataclasses
import logging
import re
from typing import Optional
import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

@dataclasses.dataclass
class LLMClient:
    """Base class for LLM clients."""

    model: str
    temperature: float = 0.7
    api_base: Optional[str] = None
    api_key: Optional[str] = None

    @staticmethod
    def split_thinking(text: str) -> tuple[str, str]:
        """Return response text and reasoning content."""
        match = _THINK_RE.search(text)
        if match is not None:
            return text[match.end() :].strip(), match.group(1).strip()
        parts = text.split("</think>", 1)
        if len(parts) == 2:
            return parts[1].strip(), parts[0].replace("<think>", "").strip()
        return text.strip(), ""

    @retry(
        retry=retry_if_exception_type((
            litellm.RateLimitError,
            litellm.ServiceUnavailableError,
            litellm.Timeout,
            litellm.APIConnectionError,
        )),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate(self, messages: list) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: List of message dictionaries

        Returns:
            Generated text response
        """
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.api_base:
            completion_kwargs["api_base"] = self.api_base
        if self.api_key:
            completion_kwargs["api_key"] = self.api_key

        response = litellm.completion(**completion_kwargs)
        response_text = response.choices[0].message.content

        return self.split_thinking(response_text)[0]
