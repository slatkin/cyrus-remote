BINDIR    := $(HOME)/.local/bin
PLUGINDIR := $(HOME)/.config/noctalia/plugins/cyrus-remote

.PHONY: install uninstall

install:
	mkdir -p $(BINDIR)
	install -m 755 cyrus.py        $(BINDIR)/cyrus-remote
	install -m 755 cyrus_daemon.py $(BINDIR)/cyrus-daemon
	install -m 755 cyrus_cmd.py    $(BINDIR)/cyrus-cmd
	ln -sf $(BINDIR)/cyrus-remote $(BINDIR)/cr
	mkdir -p $(PLUGINDIR)
	install -m 644 plugin/manifest.json $(PLUGINDIR)/
	install -m 644 plugin/Main.qml      $(PLUGINDIR)/
	install -m 644 plugin/BarWidget.qml $(PLUGINDIR)/
	@echo ""
	@echo "Add to ~/.config/noctalia/plugins.json:"
	@echo '  { "id": "cyrus-remote", "enabled": true, "path": "$(PLUGINDIR)" }'
	@echo ""
	@echo "Run the daemon: cyrus-daemon &"

uninstall:
	rm -f $(BINDIR)/cyrus-remote $(BINDIR)/cyrus-daemon $(BINDIR)/cyrus-cmd $(BINDIR)/cr
	rm -rf $(PLUGINDIR)
