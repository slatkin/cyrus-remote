BINDIR    := $(HOME)/.local/bin
PLUGINDIR := $(HOME)/.local/share/noctalia/plugins/cyrus
BARCONFIG := $(HOME)/.local/state/noctalia/settings.toml

.PHONY: install uninstall install-service

install:
	mkdir -p $(BINDIR) $(PLUGINDIR)
	install -m 755 cyrus.py        $(BINDIR)/cyrus-remote
	install -m 755 cyrus_daemon.py $(BINDIR)/cyrus-daemon
	install -m 755 cyrus_cmd.py    $(BINDIR)/cyrus-cmd
	install -m 755 cyrus_proxy.py  $(BINDIR)/cyrus-proxy
	ln -sf $(BINDIR)/cyrus-remote $(BINDIR)/cr
	install -m 644 widget/plugin.toml       $(PLUGINDIR)/
	install -m 644 widget/cyrus_volume.luau $(PLUGINDIR)/
	install -m 644 widget/cyrus_input.luau  $(PLUGINDIR)/
	@echo ""
	@echo "Bar config: $(BARCONFIG)"
	@echo "Add to start/end list: \"cyrus-volume\" and/or \"cyrus-input\""
	@echo ""
	@echo "  [widget.cyrus-volume]"
	@echo "  type = \"slatkin/cyrus:volume\""
	@echo ""
	@echo "  [widget.cyrus-input]"
	@echo "  type = \"slatkin/cyrus:input\""
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
	rm -rf $(PLUGINDIR)
