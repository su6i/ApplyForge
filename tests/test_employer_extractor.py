from src.pipeline.employer_extractor import detect_intermediary, extract_employer_info

def test_detect_intermediary():
    # Test known agencies
    assert detect_intermediary("We are Akkodis recruiting for a client") == "Akkodis"
    assert detect_intermediary("Welcome to Michael Page") == "Michael Page"
    
    # Test signals
    assert detect_intermediary("pour notre client, un grand groupe") == "Detected Intermediary"
    assert detect_intermediary("cabinet de recrutement") == "Detected Intermediary"
    assert detect_intermediary("ESN") == "Detected Intermediary"
    
    # Test direct employer
    assert detect_intermediary("Rejoignez Google") is None
    assert detect_intermediary("Startup in Paris") is None

def test_extract_employer_info(monkeypatch):
    # Mock LLM since it's an external call for intermediaries
    class MockLLM:
        def invoke(self, prompt):
            class Resp:
                content = '{"real_employer": "Client anonyme (via ESN)", "employer_type": "esn", "posting_via": "ESN"}'
            return Resp()
            
    def mock_get_llm(**kwargs):
        return MockLLM()
        
    import src.pipeline.employer_extractor
    monkeypatch.setattr(src.pipeline.employer_extractor, "get_llm", mock_get_llm)
    
    # Direct case should not use LLM
    res = extract_employer_info("We are a startup looking for...", "Awesome Corp")
    assert res["employer_type"] == "direct"
    assert res["real_employer"] == "Awesome Corp"
    assert res["posting_via"] == ""
    
    # Intermediary case should use LLM
    res = extract_employer_info("ESN recrute pour le compte de notre client final", "ESN")
    assert res["employer_type"] == "esn"
    assert res["real_employer"] == "Client anonyme (via ESN)"
    assert res["posting_via"] == "ESN"
