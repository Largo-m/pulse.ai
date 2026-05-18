import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:git2dart/git2dart.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';
import 'package:pulse_ai/features/orchestrator/service/local_git_branches_service_impl.dart';

void main() {
  group('LocalGitBranchesServiceImpl', () {
    test('returns notGitRepository for empty absolutePath', () async {
      final LocalGitBranchesServiceImpl service = LocalGitBranchesServiceImpl();

      final LocalGitBranchesResult result = await service.listLocalBranches(
        '  ',
      );

      expect(result.outcome, LocalGitBranchesOutcome.notGitRepository);
    });

    test(
      'returns success with branch names and head when repository opens',
      () async {
        final Directory directory = await Directory.systemTemp.createTemp(
          'pulse_git_branches_',
        );
        addTearDown(() async {
          if (directory.existsSync()) {
            await directory.delete(recursive: true);
          }
        });
        await Process.run('git', <String>[
          'init',
        ], workingDirectory: directory.path);
        await Process.run('git', <String>[
          'config',
          'user.email',
          'test@pulse.ai',
        ], workingDirectory: directory.path);
        await Process.run('git', <String>[
          'config',
          'user.name',
          'Pulse Test',
        ], workingDirectory: directory.path);
        await Process.run('git', <String>[
          'commit',
          '--allow-empty',
          '-m',
          'init',
        ], workingDirectory: directory.path);

        final LocalGitBranchesServiceImpl service =
            LocalGitBranchesServiceImpl();
        final LocalGitBranchesResult result = await service.listLocalBranches(
          directory.path,
        );

        expect(result.outcome, LocalGitBranchesOutcome.success);
        expect(result.branches, isNotEmpty);
        expect(result.headBranchName, isNotNull);
        expect(result.branches, contains(result.headBranchName));
      },
    );

    test(
      'returns notGitRepository when folder is not a git repository',
      () async {
        final Directory directory = await Directory.systemTemp.createTemp(
          'pulse_nogit_',
        );
        addTearDown(() async {
          if (directory.existsSync()) {
            await directory.delete(recursive: true);
          }
        });

        final LocalGitBranchesServiceImpl service =
            LocalGitBranchesServiceImpl();
        final LocalGitBranchesResult result = await service.listLocalBranches(
          directory.path,
        );

        expect(result.outcome, LocalGitBranchesOutcome.notGitRepository);
      },
    );

    test(
      'returns permissionDenied when opener throws permission error',
      () async {
        final LocalGitBranchesServiceImpl service = LocalGitBranchesServiceImpl(
          openRepository: (String path) {
            throw Exception('operation not permitted for $path');
          },
        );

        final LocalGitBranchesResult result = await service.listLocalBranches(
          '/Users/dev/repo',
        );

        expect(result.outcome, LocalGitBranchesOutcome.permissionDenied);
      },
    );

    test('returns failure when opener throws non-git error', () async {
      final LocalGitBranchesServiceImpl service = LocalGitBranchesServiceImpl(
        openRepository: (String path) {
          throw Exception('unexpected io error for $path');
        },
      );

      final LocalGitBranchesResult result = await service.listLocalBranches(
        '/Users/dev/repo',
      );

      expect(result.outcome, LocalGitBranchesOutcome.failure);
      expect(result.debugMessage, contains('unexpected io error'));
    });

    test('returns notGitRepository when opener throws ArgumentError', () async {
      final LocalGitBranchesServiceImpl service = LocalGitBranchesServiceImpl(
        openRepository: (String path) {
          throw ArgumentError('invalid repository path: $path');
        },
      );

      final LocalGitBranchesResult result = await service.listLocalBranches(
        '/invalid',
      );

      expect(result.outcome, LocalGitBranchesOutcome.notGitRepository);
    });

    test(
      'returns success with branches and null head when HEAD is detached',
      () async {
        final Directory directory = await Directory.systemTemp.createTemp(
          'pulse_git_detached_',
        );
        addTearDown(() async {
          if (directory.existsSync()) {
            await directory.delete(recursive: true);
          }
        });
        Repository.init(path: directory.path);

        final LocalGitBranchesServiceImpl service = LocalGitBranchesServiceImpl(
          readBranches: (Repository repository) {
            return const LocalGitBranchesResult(
              LocalGitBranchesOutcome.success,
              branches: <String>['main', 'feature/x'],
              headBranchName: null,
            );
          },
        );

        final LocalGitBranchesResult result = await service.listLocalBranches(
          directory.path,
        );

        expect(result.outcome, LocalGitBranchesOutcome.success);
        expect(result.branches, <String>['main', 'feature/x']);
        expect(result.headBranchName, isNull);
      },
    );
  });
}
