import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_machine_name.dart';

void main() {
  group('PrdRunMachineName', () {
    test('forProject prefixes project id with pulse-', () {
      expect(PrdRunMachineName.forProject('project-1'), 'pulse-project-1');
    });
  });
}
