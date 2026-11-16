// SPDX-License-Identifier: MIT
// Linux adapter. Upstream FUTO/LatinIME retains its own licenses.
#pragma once
#include <QString>
#include <QStringList>
#include <memory>

class FutoDictionary {
public:
    explicit FutoDictionary(const QString &path);
    ~FutoDictionary();
    FutoDictionary(const FutoDictionary &) = delete;
    FutoDictionary &operator=(const FutoDictionary &) = delete;
    QStringList suggest(const QString &word);
    int probability(const QString &word) const;
    static int importWords(const QString &words, const QString &output);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
