import 'dart:async';
import 'dart:math';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_slug_validation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

Future<void> showInitializeAgentModal(
  BuildContext context, {
  required List<LocalProjectEntity> projects,
  required String? activeProjectId,
  void Function(InitializeAgentSubmitPayload payload)? onSubmit,
}) {
  final InitializeAgentBranchesCubit branchesCubit = context
      .read<InitializeAgentBranchesCubit>();
  final MaterialLocalizations loc = MaterialLocalizations.of(context);
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: loc.modalBarrierDismissLabel,
    barrierColor: Colors.transparent,
    pageBuilder:
        (
          BuildContext dialogContext,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
        ) {
          return BlocProvider<InitializeAgentBranchesCubit>.value(
            value: branchesCubit,
            child: _InitializeAgentModalPage(
              projects: projects,
              activeProjectId: activeProjectId,
              onSubmit: onSubmit,
            ),
          );
        },
  );
}

final class _InitializeAgentModalPage extends StatefulWidget {
  const _InitializeAgentModalPage({
    required this.projects,
    required this.activeProjectId,
    this.onSubmit,
  });

  final List<LocalProjectEntity> projects;
  final String? activeProjectId;
  final void Function(InitializeAgentSubmitPayload payload)? onSubmit;

  @override
  State<_InitializeAgentModalPage> createState() =>
      _InitializeAgentModalPageState();
}

final class _InitializeAgentModalPageState
    extends State<_InitializeAgentModalPage> {
  late final TextEditingController _coreDirectiveController;
  late final TextEditingController _agentNameController;
  late final TextEditingController _slugController;
  late final ValueNotifier<String?> _projectIdNotifier;
  late final ValueNotifier<String?> _slugErrorNotifier;

  @override
  void initState() {
    super.initState();
    _coreDirectiveController = TextEditingController();
    _agentNameController = TextEditingController();
    _slugController = TextEditingController();
    _slugErrorNotifier = ValueNotifier<String?>(null);
    _slugController.addListener(_onSlugChanged);
    final List<LocalProjectEntity> projects = widget.projects;
    if (projects.isEmpty) {
      _projectIdNotifier = ValueNotifier<String?>(null);
    } else {
      String? pid = widget.activeProjectId;
      if (pid == null || !projects.any((LocalProjectEntity p) => p.id == pid)) {
        pid = projects.first.id;
      }
      _projectIdNotifier = ValueNotifier<String?>(pid);
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadBranchesForProjectId(_projectIdNotifier.value);
    });
  }

  @override
  void dispose() {
    context.read<InitializeAgentBranchesCubit>().reset();
    _slugController.removeListener(_onSlugChanged);
    _coreDirectiveController.dispose();
    _agentNameController.dispose();
    _slugController.dispose();
    _slugErrorNotifier.dispose();
    _projectIdNotifier.dispose();
    super.dispose();
  }

  LocalProjectEntity? _projectForId(String projectId) {
    for (final LocalProjectEntity project in widget.projects) {
      if (project.id == projectId) {
        return project;
      }
    }
    return null;
  }

  void _loadBranchesForProjectId(String? projectId) {
    if (projectId == null) {
      return;
    }

    final LocalProjectEntity? project = _projectForId(projectId);
    if (project == null) {
      return;
    }

    unawaited(
      context.read<InitializeAgentBranchesCubit>().loadForProject(
        absolutePath: project.canonicalPath,
        macosSecurityScopedBookmark: project.macosSecurityScopedBookmark,
      ),
    );
  }

  void _onProjectChanged(String? projectId) {
    _projectIdNotifier.value = projectId;
    _loadBranchesForProjectId(projectId);
  }

  void _onSlugChanged() {
    _slugErrorNotifier.value = validateInitializeAgentSlug(
      _slugController.text,
    );
  }

  void _onSubmitPressed(
    BuildContext context,
    String projectId,
    InitializeAgentBranchesState branchState,
  ) {
    final String? slugError = validateInitializeAgentSlug(_slugController.text);
    _slugErrorNotifier.value = slugError;
    if (slugError != null ||
        !canSubmitInitializeAgentForm(
          branchState: branchState,
          slug: _slugController.text,
        )) {
      return;
    }

    final String? branchName = branchState.selectedBranch;
    if (branchName == null) {
      return;
    }

    widget.onSubmit?.call(
      InitializeAgentSubmitPayload(
        agentName: _agentNameController.text.trim(),
        coreDirective: _coreDirectiveController.text.trim(),
        projectId: projectId,
        branchName: branchName,
        slug: _slugController.text.trim(),
      ),
    );
    Navigator.of(context).pop();
  }

  String? _branchHelperText(BranchLoadStatus status) {
    return switch (status) {
      BranchLoadStatus.loading =>
        OrchestratorStrings.initializeAgentBranchesLoading,
      BranchLoadStatus.notGitRepository =>
        OrchestratorStrings.initializeAgentBranchesNotGit,
      BranchLoadStatus.permissionDenied =>
        OrchestratorStrings.initializeAgentBranchesPermissionDenied,
      BranchLoadStatus.failure =>
        OrchestratorStrings.initializeAgentBranchesLoadFailed,
      BranchLoadStatus.initial || BranchLoadStatus.loaded => null,
    };
  }

  String? _branchSemanticsLabel(BranchLoadStatus status) {
    return switch (status) {
      BranchLoadStatus.loading =>
        OrchestratorStrings.initializeAgentBranchesLoadingSemantics,
      BranchLoadStatus.notGitRepository =>
        OrchestratorStrings.initializeAgentBranchesNotGitSemantics,
      BranchLoadStatus.permissionDenied =>
        OrchestratorStrings.initializeAgentBranchesPermissionDeniedSemantics,
      BranchLoadStatus.failure =>
        OrchestratorStrings.initializeAgentBranchesLoadFailedSemantics,
      BranchLoadStatus.initial || BranchLoadStatus.loaded => null,
    };
  }

  InputDecoration _outlineDecoration(BuildContext context, {String? hint}) {
    final TextTheme tt = Theme.of(context).textTheme;
    return InputDecoration(
      hintText: hint,
      filled: true,
      fillColor: PulseColors.surfaceContainerLowest,
      hintStyle: tt.bodyMedium?.copyWith(color: PulseColors.outline),
      floatingLabelBehavior: FloatingLabelBehavior.never,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.outlineVariant),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.outlineVariant),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.primary),
      ),
      contentPadding: PulseInsets.sidebarHeader,
    );
  }

  Widget _formLabel(TextTheme tt, String text) {
    return Text(
      text,
      style: tt.labelMedium?.copyWith(color: PulseColors.onSurfaceVariant),
    );
  }

  Widget _labeledBlock({
    required TextTheme tt,
    required String label,
    required Widget child,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        _formLabel(tt, label),
        const SizedBox(height: PulseDimensions.sectionGapSm),
        child,
      ],
    );
  }

  Widget _buildBranchControl(
    BuildContext context,
    TextTheme tt,
    InitializeAgentBranchesState branchState,
  ) {
    switch (branchState.status) {
      case BranchLoadStatus.loading:
        return const Align(
          alignment: Alignment.centerLeft,
          child: SizedBox(
            width: PulseDimensions.sidebarTreeIconSize,
            height: PulseDimensions.sidebarTreeIconSize,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: PulseColors.primary,
            ),
          ),
        );
      case BranchLoadStatus.loaded:
        final String? dropdownValue =
            branchState.selectedBranch != null &&
                branchState.branches.contains(branchState.selectedBranch)
            ? branchState.selectedBranch
            : null;

        return DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            isDense: true,
            value: dropdownValue,
            isExpanded: true,
            dropdownColor: PulseColors.surfaceContainerLowest,
            style: tt.labelLarge?.copyWith(color: PulseColors.onSurface),
            items: branchState.branches
                .map(
                  (String branch) => DropdownMenuItem<String>(
                    value: branch,
                    child: Text(branch),
                  ),
                )
                .toList(),
            onChanged: (String? value) {
              if (value != null) {
                context.read<InitializeAgentBranchesCubit>().selectBranch(
                  value,
                );
              }
            },
          ),
        );
      case BranchLoadStatus.initial:
      case BranchLoadStatus.notGitRepository:
      case BranchLoadStatus.permissionDenied:
      case BranchLoadStatus.failure:
        return DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            isDense: true,
            value: null,
            isExpanded: true,
            dropdownColor: PulseColors.surfaceContainerLowest,
            style: tt.labelLarge?.copyWith(color: PulseColors.onSurfaceVariant),
            items: const <DropdownMenuItem<String>>[],
            onChanged: null,
          ),
        );
    }
  }

  Widget _buildBranchField(TextTheme tt) {
    return _labeledBlock(
      tt: tt,
      label: OrchestratorStrings.initializeAgentBranchLabel,
      child:
          BlocBuilder<
            InitializeAgentBranchesCubit,
            InitializeAgentBranchesState
          >(
            builder:
                (
                  BuildContext context,
                  InitializeAgentBranchesState branchState,
                ) {
                  final String? helperText = _branchHelperText(
                    branchState.status,
                  );
                  final String? semanticsLabel = _branchSemanticsLabel(
                    branchState.status,
                  );
                  final bool branchFieldEnabled =
                      branchState.status == BranchLoadStatus.loaded;

                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      Semantics(
                        label: semanticsLabel,
                        enabled: branchFieldEnabled,
                        child: InputDecorator(
                          decoration: _outlineDecoration(context),
                          child: _buildBranchControl(context, tt, branchState),
                        ),
                      ),
                      if (helperText != null) ...<Widget>[
                        const SizedBox(height: PulseDimensions.sectionGapSm),
                        Text(
                          helperText,
                          style: tt.bodySmall?.copyWith(
                            color: PulseColors.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ],
                  );
                },
          ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    final double viewHeight = MediaQuery.sizeOf(context).height;
    final double maxDialogHeight = min(viewHeight * 0.92, 680);

    return SafeArea(
      child: Material(
        color: Colors.transparent,
        child: Stack(
          fit: StackFit.expand,
          children: <Widget>[
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => Navigator.of(context).pop(),
                child: ClipRect(
                  child: BackdropFilter(
                    filter: ImageFilter.blur(
                      sigmaX: PulseDimensions.modalBackdropBlurSigma,
                      sigmaY: PulseDimensions.modalBackdropBlurSigma,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: PulseColors.modalBarrierScrim.withValues(
                          alpha: 0.55,
                        ),
                      ),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ),
              ),
            ),
            Center(
              child: Material(
                color: PulseColors.surfaceContainer,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(PulseRadii.actionButton),
                  side: const BorderSide(color: PulseColors.outlineVariant),
                ),
                elevation: 12,
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: PulseDimensions.modalMaxWidth,
                    maxHeight: maxDialogHeight,
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      DecoratedBox(
                        decoration: const BoxDecoration(
                          color: PulseColors.surfaceContainerHigh,
                          border: Border(
                            bottom: BorderSide(
                              color: PulseColors.outlineVariant,
                            ),
                          ),
                        ),
                        child: Padding(
                          padding: PulseInsets.ctaCard,
                          child: Row(
                            children: <Widget>[
                              Expanded(
                                child: Text(
                                  OrchestratorStrings.initializeAgentModalTitle,
                                  style: tt.headlineSmall?.copyWith(
                                    color: PulseColors.primary,
                                  ),
                                ),
                              ),
                              IconButton(
                                visualDensity: VisualDensity.compact,
                                tooltip: OrchestratorStrings
                                    .initializeAgentCloseSemantics,
                                onPressed: () => Navigator.of(context).pop(),
                                icon: const Icon(
                                  Icons.close,
                                  color: PulseColors.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      ConstrainedBox(
                        constraints: BoxConstraints(
                          maxHeight: max(
                            PulseDimensions.modalScrollBodyMinExtent,
                            maxDialogHeight -
                                PulseDimensions
                                    .modalNonScrollingChromeHeightEstimate,
                          ),
                        ),
                        child: ListView(
                          shrinkWrap: true,
                          physics: const ClampingScrollPhysics(),
                          padding: PulseInsets.modalFormPadding,
                          children: <Widget>[
                            _labeledBlock(
                              tt: tt,
                              label:
                                  OrchestratorStrings.initializeAgentNameLabel,
                              child: TextField(
                                controller: _agentNameController,
                                style: tt.labelLarge?.copyWith(
                                  color: PulseColors.onSurface,
                                ),
                                decoration: _outlineDecoration(
                                  context,
                                  hint: OrchestratorStrings
                                      .initializeAgentNameHint,
                                ),
                              ),
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                            ValueListenableBuilder<String?>(
                              valueListenable: _slugErrorNotifier,
                              builder:
                                  (
                                    BuildContext context,
                                    String? slugError,
                                    Widget? child,
                                  ) {
                                    return _labeledBlock(
                                      tt: tt,
                                      label: OrchestratorStrings
                                          .initializeAgentSlugLabel,
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.stretch,
                                        children: <Widget>[
                                          TextField(
                                            controller: _slugController,
                                            style: tt.labelLarge?.copyWith(
                                              color: PulseColors.onSurface,
                                            ),
                                            decoration: _outlineDecoration(
                                              context,
                                              hint: OrchestratorStrings
                                                  .initializeAgentSlugHint,
                                            ),
                                          ),
                                          if (slugError != null) ...<Widget>[
                                            const SizedBox(
                                              height:
                                                  PulseDimensions.sectionGapSm,
                                            ),
                                            Text(
                                              slugError,
                                              style: tt.bodySmall?.copyWith(
                                                color: Theme.of(
                                                  context,
                                                ).colorScheme.error,
                                              ),
                                            ),
                                          ],
                                        ],
                                      ),
                                    );
                                  },
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                            _labeledBlock(
                              tt: tt,
                              label: OrchestratorStrings
                                  .initializeAgentCoreDirectiveLabel,
                              child: SizedBox(
                                height: PulseDimensions.modalTextAreaHeight,
                                child: TextField(
                                  controller: _coreDirectiveController,
                                  maxLines: null,
                                  expands: true,
                                  textAlignVertical: TextAlignVertical.top,
                                  style: tt.bodyMedium?.copyWith(
                                    color: PulseColors.onSurface,
                                  ),
                                  decoration: _outlineDecoration(
                                    context,
                                    hint: OrchestratorStrings
                                        .initializeAgentCoreDirectiveHint,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(
                              height: PulseDimensions.sectionGapLg,
                            ),
                            LayoutBuilder(
                              builder: (BuildContext context, BoxConstraints constraints) {
                                final bool stack = constraints.maxWidth < 420;
                                final Widget projectField =
                                    widget.projects.isEmpty
                                    ? _labeledBlock(
                                        tt: tt,
                                        label: OrchestratorStrings
                                            .initializeAgentProjectLabel,
                                        child: InputDecorator(
                                          decoration: _outlineDecoration(
                                            context,
                                          ),
                                          child: Text(
                                            OrchestratorStrings
                                                .initializeAgentProjectEmptyOption,
                                            style: tt.labelLarge?.copyWith(
                                              color:
                                                  PulseColors.onSurfaceVariant,
                                            ),
                                          ),
                                        ),
                                      )
                                    : _labeledBlock(
                                        tt: tt,
                                        label: OrchestratorStrings
                                            .initializeAgentProjectLabel,
                                        child: ValueListenableBuilder<String?>(
                                          valueListenable: _projectIdNotifier,
                                          builder:
                                              (
                                                BuildContext context,
                                                String? pid,
                                                Widget? child,
                                              ) {
                                                return InputDecorator(
                                                  decoration:
                                                      _outlineDecoration(
                                                        context,
                                                      ),
                                                  child: DropdownButtonHideUnderline(
                                                    child: DropdownButton<String>(
                                                      isDense: true,
                                                      value: pid,
                                                      isExpanded: true,
                                                      dropdownColor: PulseColors
                                                          .surfaceContainerLowest,
                                                      style: tt.labelLarge
                                                          ?.copyWith(
                                                            color: PulseColors
                                                                .onSurface,
                                                          ),
                                                      items: widget.projects.map((
                                                        LocalProjectEntity p,
                                                      ) {
                                                        return DropdownMenuItem<
                                                          String
                                                        >(
                                                          value: p.id,
                                                          child: Text(
                                                            p.displayName,
                                                          ),
                                                        );
                                                      }).toList(),
                                                      onChanged:
                                                          _onProjectChanged,
                                                    ),
                                                  ),
                                                );
                                              },
                                        ),
                                      );
                                final Widget branchField = _buildBranchField(
                                  tt,
                                );
                                if (stack) {
                                  return Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.stretch,
                                    children: <Widget>[
                                      projectField,
                                      const SizedBox(
                                        height: PulseDimensions.sectionGapMd,
                                      ),
                                      branchField,
                                    ],
                                  );
                                }
                                return Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Expanded(child: projectField),
                                    const SizedBox(
                                      width: PulseDimensions.sectionGapMd,
                                    ),
                                    Expanded(child: branchField),
                                  ],
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: PulseDimensions.sectionGapLg),
                      DecoratedBox(
                        decoration: const BoxDecoration(
                          color: PulseColors.surfaceContainerLow,
                          border: Border(
                            top: BorderSide(color: PulseColors.outlineVariant),
                          ),
                        ),
                        child: Padding(
                          padding: PulseInsets.modalFooterPadding,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: <Widget>[
                              TextButton(
                                onPressed: () => Navigator.of(context).pop(),
                                style: TextButton.styleFrom(
                                  foregroundColor: PulseColors.onSurfaceVariant,
                                ),
                                child: const Text(
                                  OrchestratorStrings
                                      .initializeAgentCancelButton,
                                ),
                              ),
                              const SizedBox(
                                width: PulseDimensions.sectionGapMd,
                              ),
                              ValueListenableBuilder<String?>(
                                valueListenable: _projectIdNotifier,
                                builder:
                                    (
                                      BuildContext context,
                                      String? projectId,
                                      Widget? child,
                                    ) {
                                      return ValueListenableBuilder<String?>(
                                        valueListenable: _slugErrorNotifier,
                                        builder:
                                            (
                                              BuildContext context,
                                              String? slugError,
                                              Widget? child,
                                            ) {
                                              return BlocBuilder<
                                                InitializeAgentBranchesCubit,
                                                InitializeAgentBranchesState
                                              >(
                                                builder:
                                                    (
                                                      BuildContext context,
                                                      InitializeAgentBranchesState
                                                      branchState,
                                                    ) {
                                                      final bool canSubmit =
                                                          projectId != null &&
                                                          slugError == null &&
                                                          canSubmitInitializeAgentForm(
                                                            branchState:
                                                                branchState,
                                                            slug:
                                                                _slugController
                                                                    .text,
                                                          );

                                                      return FilledButton.icon(
                                                        onPressed: canSubmit
                                                            ? () =>
                                                                  _onSubmitPressed(
                                                                    context,
                                                                    projectId,
                                                                    branchState,
                                                                  )
                                                            : null,
                                                        style:
                                                            PulseButtonStyles.filledPrimary(
                                                              context,
                                                              uppercaseLabel:
                                                                  true,
                                                            ),
                                                        label: Text(
                                                          OrchestratorStrings
                                                              .initializeAgentSubmitButton
                                                              .toUpperCase(),
                                                        ),
                                                      );
                                                    },
                                              );
                                            },
                                      );
                                    },
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
