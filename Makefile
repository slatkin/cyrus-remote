BINDIR    := $(HOME)/.local/bin
SCRIPTDIR  := $(HOME)/.config/noctalia/scripts
BARCONFIG  := $(HOME)/.local/state/noctalia/settings.toml

.PHONY: install uninstall install-service

install:
	mkdir -p $(BINDIR) $(SCRIPTDIR)
	install -m 755 cyrus.py        $(BINDIR)/cyrus-remote
	install -m 755 cyrus_daemon.py $(BINDIR)/cyrus-daemon
	install -m 755 cyrus_cmd.py    $(BINDIR)/cyrus-cmd
	install -m 755 cyrus_proxy.py  $(BINDIR)/cyrus-proxy
	ln -sf $(BINDIR)/cyrus-remote $(BINDIR)/cr
	install -m 644 widget/cyrus.lua $(SCRIPTDIR)/
	@echo ""
	@echo "Bar config: $(BARCONFIG)"
	@echo "Add to start/end list: \"cyrus\""
	@echo ""
	@echo "  [widget.cyrus]"
	@echo "  type   = \"scripted\""
	@echo "  script = \"~/.config/noctalia/scripts/cyrus.lua\""
	@echo ""
	@echo "Run the daemon: cyrus-daemon &"

install-service:
	install -m 755 cyrus_daemon.py /usr/local/bin/cyrus-daemon
	install -m 644 cyrus-daemon.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable cyrus-daemon
	@echo "Start with: systemctl start cyrus-daemon"

uninstall:
	rm -f $(BINDIR)/cyrus-remote $(BINDIR)/cyrus-daemon $(BINDIR)/cyrus-cmd $(BINDIR)/cyrus-proxy $(BINDIR)/cr
	rm -f $(SCRIPTDIR)/cyrus.lua
