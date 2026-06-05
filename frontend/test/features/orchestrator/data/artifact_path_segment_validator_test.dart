import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/data/artifact_path_segment_validator.dart';

void main() {
  group('ArtifactPathSegmentValidator', () {
    const ArtifactPathSegmentValidator validator =
        ArtifactPathSegmentValidator();

    test('validateProjectId returns right for uuid segment', () {
      expect(
        validator.validateProjectId('550e8400-e29b-41d4-a716-446655440000'),
        isA<Right<Failure, void>>(),
      );
    });

    test('validateSlug returns left when segment is empty', () {
      final Either<Failure, void> result = validator.validateSlug('');
      expect(result.isLeft(), isTrue);
      result.fold(
        (Failure failure) => expect(
          failure,
          isA<ArtifactPersistenceFailure>().having(
            (ArtifactPersistenceFailure f) => f.code,
            'code',
            ArtifactPersistenceFailureCode.invalidPathSegment,
          ),
        ),
        (_) => fail('expected left'),
      );
    });

    test('validateSlug returns left when segment contains path separator', () {
      expect(validator.validateSlug('foo/bar').isLeft(), isTrue);
      expect(validator.validateSlug(r'foo\bar').isLeft(), isTrue);
    });

    test('validateSlug returns left for parent directory tokens', () {
      expect(validator.validateSlug('..').isLeft(), isTrue);
      expect(validator.validateSlug('.').isLeft(), isTrue);
    });

    test('validateSlug returns right for kebab-case slug', () {
      expect(validator.validateSlug('my-feature').isRight(), isTrue);
    });
  });
}
