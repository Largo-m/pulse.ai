import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';

void main() {
  group('ArtifactPersistenceFailure', () {
    test('notFound exposes stable message without sdk details', () {
      const ArtifactPersistenceFailure failure =
          ArtifactPersistenceFailure.notFound();

      expect(failure.code, ArtifactPersistenceFailureCode.notFound);
      expect(failure.message, contains('PRD'));
      expect(failure.message, isNot(contains('Exception')));
    });

    test('ioError exposes generic persistence message', () {
      const ArtifactPersistenceFailure failure =
          ArtifactPersistenceFailure.ioError();

      expect(failure.code, ArtifactPersistenceFailureCode.ioError);
      expect(failure.message, 'Falha ao persistir artefato');
    });
  });
}
