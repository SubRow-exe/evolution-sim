"""Run Phase0 after applying registered physical-mode semantics corrections."""
from physical_overrides import install
install()
import run_phase0

if __name__ == "__main__":
    run_phase0.main()
