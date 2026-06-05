import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/project_path_normalizer.dart';

void main() {
  group('ProjectPathNormalizer', () {
    const ProjectPathNormalizer normalizer = ProjectPathNormalizer(
      basePath: '/Users/dev',
    );

    test('resolves relative path against base to absolute id', () {
      expect(
        normalizer.normalizeToAbsoluteId('team-repo'),
        '/Users/dev/team-repo',
      );
    });

    test('normalizes duplicate slashes in absolute path', () {
      expect(
        normalizer.normalizeToAbsoluteId('/Users/dev//team-repo/'),
        '/Users/dev/team-repo',
      );
    });

    test('returns absolute path unchanged after normalization', () {
      expect(normalizer.normalizeToAbsoluteId('/var/www/app'), '/var/www/app');
    });

    test('throws ArgumentError when raw path is empty', () {
      expect(
        () => normalizer.normalizeToAbsoluteId(''),
        throwsA(isA<ArgumentError>()),
      );
      expect(
        () => normalizer.normalizeToAbsoluteId('   '),
        throwsA(isA<ArgumentError>()),
      );
    });
  });
}
