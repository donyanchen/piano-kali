// SPDX-License-Identifier: MIT
#include "futo-core.h"
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <exception>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const auto args = app.arguments();
    QTextStream out(stdout), err(stderr);
    try {
        if (args.size() == 4 && args[1] == "--import") {
            const int count = FutoDictionary::importWords(args[2], args[3]);
            out << "Imported " << count << " words\n";
            return 0;
        }
        if (args.size() == 3 && args[1] == "--self-test") {
            FutoDictionary dictionary(args[2]);
            if (dictionary.probability("hello") < 0) throw std::runtime_error("Missing hello");
            QElapsedTimer timer;
            timer.start();
            for (int i = 0; i < 30; ++i) {
                if (!dictionary.suggest("hellp").contains("hello")) throw std::runtime_error("Typo correction failed");
                if (!dictionary.suggest("tge").contains("the")) throw std::runtime_error("Proximity correction failed");
                if (!dictionary.suggest("").isEmpty()) throw std::runtime_error("Empty input failed");
                if (!dictionary.suggest(QString(50, 'a')).isEmpty()) throw std::runtime_error("Input bound failed");
            }
            out << "PASS: native dictionary, typo/proximity correction, empty/long input; 60 queries " << timer.elapsed() << " ms\n";
            return 0;
        }
        if (args.size() != 3 || args[1] != "--stdio") {
            err << "Usage: sheng-futo-tool --import WORDS.tsv NEW_DIRECTORY | --self-test DICTIONARY | --stdio DICTIONARY\n";
            return 2;
        }
        FutoDictionary dictionary(args[2]);
        QTextStream in(stdin);
        // Test/debug transport: no file, socket or journald logging of input.
        while (!in.atEnd()) {
            auto word = in.readLine(256);
            out << QJsonDocument(QJsonObject{{"candidates", QJsonArray::fromStringList(dictionary.suggest(word))}}).toJson(QJsonDocument::Compact) << '\n';
            out.flush();
        }
        return 0;
    } catch (const std::exception &e) {
        err << e.what() << '\n';
        return 1;
    }
}
