// SPDX-License-Identifier: MIT
// Native Linux adapter; not an official FUTO product.
#include "futo-core.h"
#include <fcitx-utils/capabilityflags.h>
#include <fcitx-utils/key.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <dbus_public.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/candidatelist.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputcontextproperty.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/text.h>
#include <QFile>
#include <exception>
#include <memory>
#include <stdexcept>

namespace {
struct State : fcitx::InputContextProperty {
    QString word;
};
class UiBridge final : public fcitx::dbus::ObjectVTable<UiBridge> {
public:
    UiBridge(fcitx::Instance *instance, fcitx::dbus::Bus *bus) : instance_(instance), bus_(bus) {
        bus_->addObjectVTable("/org/sheng/FutoKeyboard", "org.sheng.FutoKeyboard1", *this);
    }
    bool commitText(const std::string &text) {
        // Only the currently registered screen-keyboard connection may commit.
        // No global text injection interface, logging or clipboard polling.
        auto *message = currentMessage();
        if (!message || text.empty() || text.size() > 64) return false;
        if (message->sender() != bus_->serviceOwner("org.sheng.FutoKeyboard.UI", 1000000)) return false;
        auto *ic = instance_->mostRecentInputContext();
        if (!ic || !ic->hasFocus() || ic->capabilityFlags().test(fcitx::CapabilityFlag::Password)
            || ic->capabilityFlags().test(fcitx::CapabilityFlag::Sensitive)) return false;
        if (!ic->inputPanel().clientPreedit().empty() || !ic->inputPanel().preedit().empty()) return false;
        const auto unicode = QString::fromUtf8(text.data(), text.size());
        if (unicode.toUtf8().toStdString() != text) return false;
        for (QChar c : unicode) if (c.isNull() || c.category() == QChar::Other_Control) return false;
        ic->commitString(text);
        return true;
    }
    FCITX_OBJECT_VTABLE_METHOD(commitText, "CommitText", "s", "b");
private:
    fcitx::Instance *instance_;
    fcitx::dbus::Bus *bus_;
};
class Engine;
class Candidate final : public fcitx::CandidateWord {
public:
    Candidate(Engine *engine, const QString &value) : CandidateWord(fcitx::Text(value.toUtf8().toStdString())), engine_(engine), value_(value) {}
    void select(fcitx::InputContext *ic) const override;
private:
    Engine *engine_;
    QString value_;
};
class Engine final : public fcitx::InputMethodEngineV2 {
public:
    explicit Engine(fcitx::Instance *instance, const QString &dictionary = "/usr/share/sheng-futo-keyboard/en_US") : instance_(instance), factory_([](fcitx::InputContext &) { return new State; }) {
        if (!instance_->inputContextManager().registerProperty("shengFutoState", &factory_))
            throw std::runtime_error("Could not register FUTO input context state");
        // Only the fixed public dictionary is read. No per-user learning store.
        dictionary_ = std::make_unique<FutoDictionary>(dictionary);
        if (auto *module = instance_->addonManager().addon("dbus")) {
            if (auto *bus = module->call<fcitx::IDBusModule::bus>())
                uiBridge_ = std::make_unique<UiBridge>(instance_, bus);
        }
        capabilityWatcher_ = instance_->watchEvent(fcitx::EventType::InputContextCapabilityChanged,
            fcitx::EventWatcherPhase::Default, [this](fcitx::Event &event) {
                auto *ic = static_cast<fcitx::InputContextEvent &>(event).inputContext();
                if ((ic->capabilityFlags().test(fcitx::CapabilityFlag::Password)
                     || ic->capabilityFlags().test(fcitx::CapabilityFlag::Sensitive))
                    && !ic->propertyFor(&factory_)->word.isEmpty()) clear(ic);
            });
    }
    void reset(const fcitx::InputMethodEntry &, fcitx::InputContextEvent &event) override { clear(event.inputContext()); }
    void deactivate(const fcitx::InputMethodEntry &, fcitx::InputContextEvent &event) override {
        // Never submit a partly entered word to a different focus target.
        clear(event.inputContext());
    }
    void commit(fcitx::InputContext *ic, const QString &value, bool space = false) {
        ic->commitString((value + (space ? " " : "")).toUtf8().toStdString());
        clear(ic);
    }
    void keyEvent(const fcitx::InputMethodEntry &, fcitx::KeyEvent &event) override {
        if (event.isRelease()) return;
        auto *ic = event.inputContext();
        auto *state = ic->propertyFor(&factory_);
        const auto key = event.key();
        if (ic->capabilityFlags().test(fcitx::CapabilityFlag::Password) || ic->capabilityFlags().test(fcitx::CapabilityFlag::Sensitive)) {
            clear(ic);
            return;
        }
        if (key.states().test(fcitx::KeyState::Ctrl) || key.states().test(fcitx::KeyState::Alt) || key.states().test(fcitx::KeyState::Super)) {
            if (!state->word.isEmpty()) commit(ic, state->word);
            return;
        }
        const auto sym = key.sym();
        if ((sym >= FcitxKey_a && sym <= FcitxKey_z) || (sym >= FcitxKey_A && sym <= FcitxKey_Z)
            || (sym == FcitxKey_apostrophe && !state->word.isEmpty())) {
            if (state->word.size() >= 46) commit(ic, state->word);
            state->word += QChar(static_cast<char16_t>(sym));
            update(ic);
            event.filterAndAccept();
            return;
        }
        if (state->word.isEmpty()) return;
        if (sym == FcitxKey_BackSpace) {
            state->word.chop(1);
            update(ic);
            event.filterAndAccept();
        } else if (sym == FcitxKey_Escape) {
            clear(ic);
            event.filterAndAccept();
        } else if (sym == FcitxKey_space) {
            // Typed text remains the default. A correction needs an explicit tap.
            commit(ic, state->word, true);
            event.filterAndAccept();
        } else if (sym >= FcitxKey_1 && sym <= FcitxKey_8) {
            auto list = ic->inputPanel().candidateList();
            const int index = sym - FcitxKey_1;
            if (list && index < list->size()) {
                list->candidate(index).select(ic);
                event.filterAndAccept();
            } else {
                commit(ic, state->word);
            }
        } else {
            commit(ic, state->word);
        }
    }
private:
    void clear(fcitx::InputContext *ic) {
        ic->propertyFor(&factory_)->word.clear();
        ic->inputPanel().reset();
        ic->updatePreedit();
        ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
    }
    void update(fcitx::InputContext *ic) {
        const auto word = ic->propertyFor(&factory_)->word;
        ic->inputPanel().reset();
        if (!word.isEmpty()) {
            auto bytes = word.toUtf8().toStdString();
            fcitx::Text preedit(bytes, fcitx::TextFormatFlag::Underline);
            preedit.setCursor(bytes.size());
            if (ic->capabilityFlags().test(fcitx::CapabilityFlag::Preedit)) ic->inputPanel().setClientPreedit(preedit);
            else ic->inputPanel().setPreedit(preedit);
            auto list = std::make_unique<fcitx::CommonCandidateList>();
            list->setPageSize(8);
            QStringList suggestions{word};
            suggestions.append(dictionary_->suggest(word));
            suggestions.removeDuplicates();
            for (const auto &candidate : suggestions.mid(0, 8)) list->append<Candidate>(this, candidate);
            ic->inputPanel().setCandidateList(std::move(list));
        }
        ic->updatePreedit();
        ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
    }
    fcitx::Instance *instance_;
    fcitx::FactoryFor<State> factory_;
    std::unique_ptr<FutoDictionary> dictionary_;
    std::unique_ptr<fcitx::HandlerTableEntry<fcitx::EventHandler>> capabilityWatcher_;
    std::unique_ptr<UiBridge> uiBridge_;
};
void Candidate::select(fcitx::InputContext *ic) const { engine_->commit(ic, value_, true); }
class Factory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        try { return new Engine(manager->instance()); }
        catch (const std::exception &) { return nullptr; } // Fcitx and the Chinese engine stay usable.
    }
};
}
FCITX_ADDON_FACTORY(Factory);
