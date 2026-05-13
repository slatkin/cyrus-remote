BINDIR := $(HOME)/.local/bin

.PHONY: install uninstall

install:
	install -m 755 cyrus_tui.py $(BINDIR)/cyrus-remote
	ln -sf $(BINDIR)/cyrus-remote $(BINDIR)/cr

uninstall:
	rm -f $(BINDIR)/cyrus-remote $(BINDIR)/cr
