import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';

final class ArtifactPathSegmentValidator {
  const ArtifactPathSegmentValidator();

  Either<Failure, void> validateProjectId(String projectId) {
    return _validateSegment(projectId, 'projectId');
  }

  Either<Failure, void> validateSlug(String slug) {
    return _validateSegment(slug, 'slug');
  }

  Either<Failure, void> _validateSegment(String value, String label) {
    if (value.isEmpty) {
      return left(ArtifactPersistenceFailure.invalidPathSegment(label));
    }

    if (value == '.' || value == '..') {
      return left(ArtifactPersistenceFailure.invalidPathSegment(label));
    }

    const String forbidden = '/\\';
    for (final int codeUnit in value.codeUnits) {
      if (forbidden.codeUnitAt(0) == codeUnit ||
          forbidden.codeUnitAt(1) == codeUnit ||
          codeUnit == 0) {
        return left(ArtifactPersistenceFailure.invalidPathSegment(label));
      }
    }

    return right(null);
  }
}
