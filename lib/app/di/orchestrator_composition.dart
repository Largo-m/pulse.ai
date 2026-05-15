import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/features/orchestrator/data/recent_projects_local_storage.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/recent_projects_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/service/local_directory_picker_service_impl.dart';
import 'package:shared_preferences/shared_preferences.dart';

final class OrchestratorComposition {
  OrchestratorComposition({
    required this.recentProjectsRepository,
    required this.recentProjectsCubit,
    required this.importFlowCubit,
  });

  final RecentProjectsRepository recentProjectsRepository;
  final RecentProjectsCubit recentProjectsCubit;
  final ImportFlowCubit importFlowCubit;

  static Future<OrchestratorComposition> create() async {
    final SharedPreferences preferences = await SharedPreferences.getInstance();
    final RecentProjectsLocalStorage storage = RecentProjectsLocalStorage(
      preferences,
    );
    final RecentProjectsRepository repository = RecentProjectsRepositoryImpl(
      storage,
    );
    final LocalDirectoryPickerServiceImpl pickerService =
        LocalDirectoryPickerServiceImpl();

    final ListRecentProjectsUseCase listRecentProjectsUseCase =
        ListRecentProjectsUseCase(repository);
    final SelectActiveProjectUseCase selectActiveProjectUseCase =
        SelectActiveProjectUseCase(repository);
    final ImportLocalProjectUseCase importLocalProjectUseCase =
        ImportLocalProjectUseCase(
          repository: repository,
          pickerService: pickerService,
        );

    final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
      listRecentProjectsUseCase: listRecentProjectsUseCase,
      selectActiveProjectUseCase: selectActiveProjectUseCase,
    );
    final ImportFlowCubit importFlowCubit = ImportFlowCubit(
      importLocalProjectUseCase: importLocalProjectUseCase,
    );

    return OrchestratorComposition(
      recentProjectsRepository: repository,
      recentProjectsCubit: recentProjectsCubit,
      importFlowCubit: importFlowCubit,
    );
  }

  void dispose() {
    unawaited(recentProjectsCubit.close());
    unawaited(importFlowCubit.close());
  }
}

class OrchestratorCompositionScope extends StatefulWidget {
  const OrchestratorCompositionScope({required this.child, super.key});

  final Widget child;

  @override
  State<OrchestratorCompositionScope> createState() =>
      _OrchestratorCompositionScopeState();
}

class _OrchestratorCompositionScopeState
    extends State<OrchestratorCompositionScope> {
  late final Future<OrchestratorComposition> _compositionFuture =
      OrchestratorComposition.create();
  OrchestratorComposition? _composition;

  @override
  void dispose() {
    _composition?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<OrchestratorComposition>(
      future: _compositionFuture,
      builder:
          (
            BuildContext context,
            AsyncSnapshot<OrchestratorComposition> snapshot,
          ) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const SizedBox.shrink();
            }

            if (!snapshot.hasData) {
              return const SizedBox.shrink();
            }

            _composition ??= snapshot.data!;
            final OrchestratorComposition composition = _composition!;

            return MultiRepositoryProvider(
              providers: <RepositoryProvider<dynamic>>[
                RepositoryProvider<RecentProjectsRepository>.value(
                  value: composition.recentProjectsRepository,
                ),
              ],
              child: MultiBlocProvider(
                providers: <BlocProvider<dynamic>>[
                  BlocProvider<RecentProjectsCubit>.value(
                    value: composition.recentProjectsCubit,
                  ),
                  BlocProvider<ImportFlowCubit>.value(
                    value: composition.importFlowCubit,
                  ),
                ],
                child: widget.child,
              ),
            );
          },
    );
  }
}
