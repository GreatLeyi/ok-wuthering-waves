if __name__ == '__main__':
    # Mobile-mode entry point for ok-ww running against MuMu Player 12.
    #
    # Architecture: see ai-doc/mobile-port-plan.md
    # Plugin code:  plugins/mumu12/
    #
    # PC mode is unaffected — run main.py / main_debug.py as before.
    from config import config
    from ok import OK
    from plugins.mumu12 import apply_to

    OK(apply_to(config)).start()
