import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/service/github_remote_url_normalizer.dart';

void main() {
  group('normalizeToGithubHttpsUrl', () {
    test('normalizes https URL with .git suffix', () {
      expect(
        normalizeToGithubHttpsUrl('https://github.com/acme/repo.git'),
        'https://github.com/acme/repo',
      );
    });

    test('normalizes git@github.com scp-style URL', () {
      expect(
        normalizeToGithubHttpsUrl(
          'git@github.com:jonathancosta/stock-trader.git',
        ),
        'https://github.com/jonathancosta/stock-trader',
      );
    });

    test('returns null for non-GitHub host', () {
      expect(
        normalizeToGithubHttpsUrl('https://gitlab.com/acme/repo.git'),
        isNull,
      );
    });
  });
}
