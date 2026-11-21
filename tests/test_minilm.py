"""Offline fixture for installations with the optional pinned CPU model."""
from importlib.util import find_spec
import unittest
from unittest.mock import patch

from market_intel.gaps import _leftover_clusters
from market_intel.minilm import FILES, model_dir


class LocalMiniLMTests(unittest.TestCase):
    def test_two_distinct_needs_cluster_without_network(self):
        if not all((model_dir()/name).is_file() for name in FILES):
            self.skipTest("Local MiniLM weights are optional")
        if not all(find_spec(name) for name in ("onnxruntime","tokenizers","sklearn")):
            self.skipTest("Local MiniLM runtime is optional")
        bottles = ["a larger bottle would be useful","it would be useful to have a larger bottle"]
        pumps = ["a pump dispenser would be hygienic","it would be hygienic to have a pump dispenser"]
        inputs = sorted(bottles + pumps)
        with patch("socket.socket.connect", side_effect=AssertionError("network request during inference")):
            result = _leftover_clusters(inputs)
            self.assertEqual(result,_leftover_clusters(inputs))
        groups, method = result
        self.assertEqual({frozenset(g) for g in groups},{frozenset(bottles),frozenset(pumps)})
        self.assertIn("MiniLM",method)
