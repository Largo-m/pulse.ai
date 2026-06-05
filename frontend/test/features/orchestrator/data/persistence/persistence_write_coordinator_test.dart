import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/data/persistence/persistence_write_coordinator.dart';

void main() {
  group('PersistenceWriteCoordinator', () {
    const PersistenceWriteCoordinator coordinator =
        PersistenceWriteCoordinator();

    test(
      'rolls back filesystem when hive commit fails after filesystem success',
      () async {
        bool filesystemCommitted = false;
        bool filesystemRolledBack = false;

        final Either<Failure, String> result = await coordinator
            .commitFilesystemFirst<String>(
              filesystemCommit: () async {
                filesystemCommitted = true;
                return right(null);
              },
              hiveCommit: () async {
                return left(const WorkflowPersistenceFailure.hiveError());
              },
              rollbackFilesystem: () async {
                filesystemRolledBack = true;
              },
            );

        expect(result.isLeft(), isTrue);
        expect(filesystemCommitted, isTrue);
        expect(filesystemRolledBack, isTrue);
      },
    );

    test('returns filesystem failure without hive commit', () async {
      bool hiveCalled = false;

      final Either<Failure, String> result = await coordinator
          .commitFilesystemFirst<String>(
            filesystemCommit: () async {
              return left(const WorkflowPersistenceFailure.hiveError());
            },
            hiveCommit: () async {
              hiveCalled = true;
              return right('ok');
            },
            rollbackFilesystem: () async {},
          );

      expect(result.isLeft(), isTrue);
      expect(hiveCalled, isFalse);
    });
  });
}
