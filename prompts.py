"""Dynamic prompt loader - Load prompts based on PROMPT_LANGUAGE env variable"""
from config import PROMPT_LANGUAGE
import importlib.util
import sys
from pathlib import Path


# Map of supported languages and their file names
SUPPORTED_LANGUAGES = {
    "vi": "prompts.vi",
    "en": "prompts.en",
    "ja": "prompts.ja"
}


def _load_prompt_module():
    """
    Dynamically load the appropriate prompt module based on PROMPT_LANGUAGE
    
    Returns:
        module: The loaded prompt module
    
    Raises:
        ValueError: If PROMPT_LANGUAGE is not supported
    """
    if PROMPT_LANGUAGE not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"⚠️ PROMPT_LANGUAGE '{PROMPT_LANGUAGE}' is not supported! "
            f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )
    
    module_filename = SUPPORTED_LANGUAGES[PROMPT_LANGUAGE]
    module_path = Path(__file__).parent / f"{module_filename}.py"
    
    if not module_path.exists():
        raise ImportError(
            f"⚠️ Cannot load module '{module_filename}'. "
            f"Please ensure file '{module_path}' exists!"
        )
    
    # Load module from file path
    spec = importlib.util.spec_from_file_location(module_filename, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"⚠️ Cannot create spec for module '{module_filename}'")
    
    prompt_module = importlib.util.module_from_spec(spec)
    sys.modules[module_filename] = prompt_module
    spec.loader.exec_module(prompt_module)
    
    print(f"✅ Loaded prompt module: {module_filename} (language: {PROMPT_LANGUAGE})")
    return prompt_module


# Load the prompt module
_prompt_module = _load_prompt_module()


# Export all functions from the loaded module
get_extraction_prompt = _prompt_module.get_extraction_prompt
get_cv_extraction_prompt = _prompt_module.get_cv_extraction_prompt
get_cv_matching_prompt = _prompt_module.get_cv_matching_prompt
get_system_message = _prompt_module.get_system_message
get_stage3_advanced_prompt = _prompt_module.get_stage3_advanced_prompt
format_cv_contents = _prompt_module.format_cv_contents


# Export the list of exported functions for introspection
__all__ = [
    'get_extraction_prompt',
    'get_cv_extraction_prompt',
    'get_cv_matching_prompt',
    'get_system_message',
    'get_stage3_advanced_prompt',
    'format_cv_contents'
]

