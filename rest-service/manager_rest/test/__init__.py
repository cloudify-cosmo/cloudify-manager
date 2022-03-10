def _assertDictContainsSubset(subset, containing_dict):
    assert subset.items() <= containing_dict.items()
