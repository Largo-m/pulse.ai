import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';
import 'package:pulse_ai/features/orchestrator/service/local_directory_picker_service_impl.dart';

void main() {
  group('LocalDirectoryPickerServiceImpl', () {
    test('returns cancelled when platform returns null', () async {
      final LocalDirectoryPickerServiceImpl service =
          LocalDirectoryPickerServiceImpl(pickDirectory: () async => null);

      final DirectoryPickResult result = await service.pickDirectory();

      expect(result.outcome, DirectoryPickOutcome.cancelled);
      expect(result.absolutePath, isNull);
    });

    test(
      'returns success with absolute path when platform returns path',
      () async {
        final LocalDirectoryPickerServiceImpl service =
            LocalDirectoryPickerServiceImpl(
              pickDirectory: () async => '/Users/dev/team-repo',
            );

        final DirectoryPickResult result = await service.pickDirectory();

        expect(result.outcome, DirectoryPickOutcome.success);
        expect(result.absolutePath, '/Users/dev/team-repo');
      },
    );

    test('returns failure with message when platform throws', () async {
      final LocalDirectoryPickerServiceImpl service =
          LocalDirectoryPickerServiceImpl(
            pickDirectory: () async {
              throw Exception('permission denied');
            },
          );

      final DirectoryPickResult result = await service.pickDirectory();

      expect(result.outcome, DirectoryPickOutcome.failure);
      expect(result.failureMessage, contains('permission denied'));
    });
  });
}
