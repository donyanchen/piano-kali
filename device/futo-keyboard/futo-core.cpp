// SPDX-License-Identifier: MIT
#include "futo-core.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QTextStream>
#include <algorithm>
#include <array>
#include <stdexcept>
#include <vector>
#include "dictionary/property/ngram_context.h"
#include "dictionary/property/unigram_property.h"
#include "dictionary/structure/dictionary_structure_with_buffer_policy_factory.h"
#include "suggest/core/dictionary/dictionary.h"
#include "suggest/core/layout/proximity_info.h"
#include "suggest/core/result/suggestion_results.h"
#include "suggest/core/session/dic_traverse_session.h"
#include "suggest/core/suggest_options.h"

using namespace latinime;
namespace {
std::vector<int> codepoints(const QString &word) {
    const auto data = word.toUcs4();
    return {data.begin(), data.end()};
}
std::unique_ptr<Dictionary> openDictionary(const QString &path, bool writable) {
    auto bytes = QFile::encodeName(path);
    auto policy = DictionaryStructureWithBufferPolicyFactory::newPolicyForExistingDictFile(
        bytes.constData(), 0, 0, writable);
    if (!policy) throw std::runtime_error("Could not open FUTO dictionary");
    return std::make_unique<Dictionary>(nullptr, std::move(policy));
}
}
struct FutoDictionary::Impl {
    std::unique_ptr<Dictionary> dictionary;
    std::unique_ptr<ProximityInfo> proximity;
    DicTraverseSession session{nullptr, nullptr, true};
    explicit Impl(const QString &path) : dictionary(openDictionary(path, false)) {
        // The pinned Default/qwerty.yaml layout, expressed in normalized units.
        const std::array<std::string, 3> rows{"qwertyuiop", "asdfghjkl", "zxcvbnm"};
        std::vector<int> xs, ys, ws, hs, codes;
        for (int row = 0; row < 3; ++row) {
            int column = 0;
            for (char c : rows[row]) {
                xs.push_back((row == 1 ? 50 : row == 2 ? 150 : 0) + column++ * 100);
                ys.push_back(row * 100);
                ws.push_back(100); hs.push_back(100); codes.push_back(c);
            }
        }
        proximity = std::make_unique<ProximityInfo>(1000, 300, static_cast<int>(codes.size()),
            xs.data(), ys.data(), ws.data(), hs.data(), codes.data());
    }
};
FutoDictionary::FutoDictionary(const QString &path) : impl_(std::make_unique<Impl>(path)) {}
FutoDictionary::~FutoDictionary() = default;
int FutoDictionary::probability(const QString &word) const {
    const auto points = codepoints(word);
    if (points.empty() || points.size() >= MAX_WORD_LENGTH) return NOT_A_PROBABILITY;
    return impl_->dictionary->getProbability(CodePointArrayView(points.data(), points.size()));
}
QStringList FutoDictionary::suggest(const QString &word) {
    auto points = codepoints(word.toLower());
    if (points.empty() || points.size() >= MAX_WORD_LENGTH) return {};
    std::array<int, MAX_WORD_LENGTH> xs, ys, times{}, pointers{};
    xs.fill(NOT_A_COORDINATE); ys.fill(NOT_A_COORDINATE);
    const int options[] = {0, 1, 1, 0, 1000};
    SuggestOptions settings(options, 5);
    NgramContext context;
    SuggestionResults result(8);
    impl_->dictionary->getSuggestions(impl_->proximity.get(), &impl_->session,
        xs.data(), ys.data(), times.data(), pointers.data(), points.data(), points.size(),
        &context, &settings, NOT_A_WEIGHT_OF_LANG_MODEL_VS_SPATIAL_MODEL, &result);
    QStringList words;
    for (const auto &candidate : result.linuxSuggestions()) {
        char utf8[MAX_WORD_LENGTH * 6 + 1];
        intArrayToCharArray(candidate.getCodePoint(), candidate.getCodePointCount(), utf8, sizeof(utf8));
        auto text = QString::fromUtf8(utf8);
        if (word.front().isUpper() && !text.isEmpty()) text[0] = text.front().toUpper();
        if (!words.contains(text)) words.push_back(text);
    }
    return words;
}
int FutoDictionary::importWords(const QString &words, const QString &output) {
    // Operates only on a fresh build directory, never on user learning data.
    if (QFile::exists(output)) throw std::runtime_error("Output dictionary already exists");
    QFile input(words);
    if (!input.open(QIODevice::ReadOnly | QIODevice::Text)) throw std::runtime_error("Missing word list");
    DictionaryHeaderStructurePolicy::AttributeMap attributes;
    attributes[codepoints("dictionary")] = codepoints("futo-linux-en_US");
    attributes[codepoints("MAX_UNIGRAM_ENTRY_COUNT")] = codepoints("300000");
    auto policy = DictionaryStructureWithBufferPolicyFactory::newPolicyForOnMemoryDict(403, codepoints("en_US"), &attributes);
    if (!policy) throw std::runtime_error("Could not create dictionary");
    auto dict = std::make_unique<Dictionary>(nullptr, std::move(policy));
    QDir().mkpath(QFileInfo(output).absolutePath());
    const auto name = QFile::encodeName(output);
    int count = 0;
    QTextStream stream(&input);
    while (!stream.atEnd()) {
        auto fields = stream.readLine().split('\t');
        if (fields.size() != 2) continue;
        bool ok = false;
        const int frequency = fields[1].toInt(&ok);
        const auto word = codepoints(fields[0]);
        if (!ok || frequency < 1 || frequency > 255 || word.empty() || word.size() >= MAX_WORD_LENGTH) continue;
        UnigramProperty property(false, false, false, frequency, HistoricalInfo());
        if (!dict->addUnigramEntry(CodePointArrayView(word.data(), word.size()), &property))
            throw std::runtime_error("Dictionary insertion failed");
        ++count;
        if (count % 500 == 0 && dict->needsToRunGC(false)) {
            if (!dict->flushWithGC(name.constData())) throw std::runtime_error("Dictionary GC failed");
            dict = openDictionary(output, true);
        }
    }
    if (count == 0 || !dict->flushWithGC(name.constData())) throw std::runtime_error("Empty or unflushable dictionary");
    return count;
}
