// SPDX-License-Identifier: MIT
// Runs against an isolated Fcitx Instance, never the user's input session.
#include "fcitx-engine.cpp"
#include <fcitx/inputmethodentry.h>
#include <fcitx-utils/eventdispatcher.h>
#include <QCoreApplication>
#include <QTemporaryDir>
#include <iostream>
#include <stdexcept>

namespace {
class Context final : public fcitx::InputContext {
public:
    explicit Context(fcitx::InputContextManager &manager) : InputContext(manager, "sheng-futo-test") {}
    ~Context() override { destroy(); }
    const char *frontend() const override { return "test"; }
    void commitStringImpl(const std::string &value) override { committed += value; }
    void deleteSurroundingTextImpl(int, unsigned int) override {}
    void forwardKeyImpl(const fcitx::ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {}
    std::string committed;
};
void require(bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
}
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (argc != 2) return 2;
    QTemporaryDir data;
    qputenv("XDG_CONFIG_HOME", (data.path() + "/config").toUtf8());
    qputenv("XDG_DATA_HOME", (data.path() + "/data").toUtf8());
    qputenv("XDG_CACHE_HOME", (data.path() + "/cache").toUtf8());
    char name[] = "sheng-futo-test", disable[] = "--disable=all";
    char *options[] = {name, disable};
    try {
        fcitx::Instance instance(2, options);
        int result = 0;
        instance.eventDispatcher().schedule([&] {
        try {
        Engine engine(&instance, QString::fromLocal8Bit(argv[1]));
        Context first(instance.inputContextManager()), second(instance.inputContextManager());
        first.setCapabilityFlags(fcitx::CapabilityFlag::Preedit);
        second.setCapabilityFlags(fcitx::CapabilityFlag::Preedit);
        fcitx::InputMethodEntry entry("sheng-futo", "FUTO test", "en_US", "sheng-futo");
        auto send = [&](Context &context, const std::string &key, bool release = false) {
            fcitx::KeyEvent event(&context, fcitx::Key(key), release);
            engine.keyEvent(entry, event);
            return event.accepted();
        };
        first.focusIn();
        for (const auto *key : {"h", "e", "l", "l", "p"}) require(send(first, key), "Composition key leaked");
        require(first.committed.empty(), "Premature commit");
        auto candidates = first.inputPanel().candidateList();
        require(candidates && candidates->size() >= 2, "Candidate UI missing");
        bool selected = false;
        for (int i = 0; i < candidates->size(); ++i) {
            if (candidates->candidate(i).text().toString() == "hello") {
                candidates->candidate(i).select(&first); selected = true; break;
            }
        }
        require(selected && first.committed == "hello ", "Candidate commit failed");
        require(!first.inputPanel().candidateList(), "Candidate state not reset");
        require(!send(first, "h", true), "Release key consumed");
        send(first, "a"); send(first, "BackSpace");
        require(first.inputPanel().clientPreedit().empty(), "Backspace preedit failed");
        send(first, "t"); send(first, "e"); send(first, "s"); send(first, "t"); send(first, "space");
        require(first.committed == "hello test ", "Typed text changed on space");
        send(first, "a");
        fcitx::InputContextEvent reset(&first, fcitx::EventType::InputContextReset);
        engine.reset(entry, reset);
        require(first.inputPanel().clientPreedit().empty(), "Focus reset leaked preedit");
        second.focusIn();
        send(second, "b"); send(second, "space");
        require(second.committed == "b ", "Input contexts were mixed");
        send(second, "p");
        second.setCapabilityFlags(fcitx::CapabilityFlag::Password);
        require(!second.inputPanel().candidateList(), "Candidates survived a sensitive capability change");
        require(!send(second, "x"), "Password key intercepted");
        require(!second.inputPanel().candidateList(), "Password candidates exposed");
        second.setCapabilityFlags(fcitx::CapabilityFlag::Sensitive);
        require(!send(second, "x"), "Sensitive field key intercepted");
        std::cout << "PASS: Fcitx preedit, candidates, commit, backspace, space, release, context isolation, password/sensitive bypass\n";
        } catch (const std::exception &e) {
            std::cerr << e.what() << '\n';
            result = 1;
        }
        instance.exit();
        });
        instance.exec();
        return result;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
