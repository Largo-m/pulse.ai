import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';

void main() {
  group('WorkflowKey', () {
    test('compose and parse round-trip projectId and slug', () {
      const String projectId = '550e8400-e29b-41d4-a716-446655440000';
      const String slug = 'payments-api';
      final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
      final ({String projectId, String slug})? parsed = WorkflowKey.parse(key);

      expect(parsed?.projectId, projectId);
      expect(parsed?.slug, slug);
    });

    test('parse returns null for invalid key', () {
      expect(WorkflowKey.parse('invalid'), isNull);
    });
  });
}
