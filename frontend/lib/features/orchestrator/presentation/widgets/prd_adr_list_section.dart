import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_adr_list_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/prd_artifact_card.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/workflow_section_header.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

final class PrdAdrListSection extends StatelessWidget {
  const PrdAdrListSection({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<PrdAdrListCubit, PrdAdrListState>(
      builder: (BuildContext context, PrdAdrListState state) {
        if (state.loadStatus == PrdAdrListLoadStatus.idle ||
            state.loadStatus == PrdAdrListLoadStatus.loading) {
          return const SizedBox.shrink();
        }

        if (state.loadStatus == PrdAdrListLoadStatus.error) {
          return _AdrListShell(
            child: Text(
              prdArtifactFailureMessageForKey(
                state.failureMessageKey ??
                    PrdArtifactFailureMessageKeys.adrListLoadFailed,
              ),
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: PulseColors.onSurfaceVariant,
              ),
            ),
          );
        }

        if (state.entries.isEmpty) {
          return const SizedBox.shrink();
        }

        return _AdrListShell(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: _adrCards(context, state.entries),
          ),
        );
      },
    );
  }

  List<Widget> _adrCards(BuildContext context, List<AdrEntry> entries) {
    final List<Widget> cards = <Widget>[];
    for (int index = 0; index < entries.length; index++) {
      if (index > 0) {
        cards.add(const SizedBox(height: PulseDimensions.sectionGapMd));
      }
      final AdrEntry entry = entries[index];
      final String preview = entry.markdown.trim();
      cards.add(
        PrdArtifactCard(
          fileName: entry.fileName,
          footer: const SizedBox.shrink(),
          child: Padding(
            padding: PulseInsets.prdArtifactTitleBar,
            child: Text(
              preview.isEmpty
                  ? prdArtifactFailureMessageForKey(
                      PrdArtifactFailureMessageKeys.missingArtifact,
                    )
                  : preview,
              maxLines: 8,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: PulseColors.onSurface),
            ),
          ),
        ),
      );
    }
    return cards;
  }
}

final class _AdrListShell extends StatelessWidget {
  const _AdrListShell({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: OrchestratorStrings.prdAdrListSectionSemantics,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: PulseColors.surfaceContainer,
          borderRadius: BorderRadius.circular(PulseRadii.workflowStreamPanel),
          border: Border.all(
            color: PulseColors.outlineVariant,
            width: PulseDimensions.workflowStreamPanelBorderWidth,
          ),
        ),
        child: Padding(
          padding: PulseInsets.workflowStreamPanel,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              const WorkflowSectionHeader(
                icon: Icons.account_tree_outlined,
                title: OrchestratorStrings.prdAdrListSectionTitle,
              ),
              const SizedBox(height: PulseDimensions.sectionGapMd),
              child,
            ],
          ),
        ),
      ),
    );
  }
}
