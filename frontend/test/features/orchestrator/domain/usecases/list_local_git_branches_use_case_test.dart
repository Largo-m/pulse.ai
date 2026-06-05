import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';

import 'fake_local_git_branches_service.dart';

void main() {
  group('ListLocalGitBranchesUseCase', () {
    late FakeLocalGitBranchesService service;
    late ListLocalGitBranchesUseCase useCase;

    setUp(() {
      service = FakeLocalGitBranchesService();
      useCase = ListLocalGitBranchesUseCase(service: service);
    });

    test('delegates absolutePath to service listLocalBranches', () async {
      service.nextResult = const LocalGitBranchesResult(
        LocalGitBranchesOutcome.success,
        branches: <String>['main'],
        headBranchName: 'main',
      );

      final LocalGitBranchesResult result = await useCase.call(
        absolutePath: '/Users/dev/team-repo',
        macosSecurityScopedBookmark: 'bookmark-data',
      );

      expect(service.listLocalBranchesCallCount, 1);
      expect(service.lastAbsolutePath, '/Users/dev/team-repo');
      expect(service.lastMacosSecurityScopedBookmark, 'bookmark-data');
      expect(result.outcome, LocalGitBranchesOutcome.success);
      expect(result.branches, <String>['main']);
      expect(result.headBranchName, 'main');
    });

    test('propagates notGitRepository outcome from service', () async {
      service.nextResult = const LocalGitBranchesResult(
        LocalGitBranchesOutcome.notGitRepository,
      );

      final LocalGitBranchesResult result = await useCase.call(
        absolutePath: '/tmp/plain',
      );

      expect(result.outcome, LocalGitBranchesOutcome.notGitRepository);
    });

    test('propagates failure outcome from service', () async {
      service.nextResult = const LocalGitBranchesResult(
        LocalGitBranchesOutcome.failure,
        debugMessage: 'io error',
      );

      final LocalGitBranchesResult result = await useCase.call(
        absolutePath: '/tmp/broken',
      );

      expect(result.outcome, LocalGitBranchesOutcome.failure);
      expect(result.debugMessage, 'io error');
    });
  });
}
