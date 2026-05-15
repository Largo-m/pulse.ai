import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_insets.dart';

final class OrchestratorAppTopBar extends StatelessWidget {
  const OrchestratorAppTopBar({super.key, required this.onPlaceholder});

  final VoidCallback onPlaceholder;

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    return Material(
      color: GovernanceColors.surfaceContainerLowest,
      child: SizedBox(
        height: GovernanceDimensions.appTopBarHeight,
        child: DecoratedBox(
          decoration: const BoxDecoration(
            border: Border(
              bottom: BorderSide(color: GovernanceColors.outlineVariant),
            ),
          ),
          child: Padding(
            padding: GovernanceInsets.appTopBar,
            child: Row(
              children: [
                Text(
                  'Pulse.AI',
                  style: tt.labelMedium?.copyWith(
                    color: GovernanceColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Container(
                  width: GovernanceDimensions.brandDividerWidth,
                  height: GovernanceDimensions.brandDividerHeight,
                  margin: const EdgeInsets.symmetric(
                    horizontal:
                        GovernanceDimensions.brandDividerHorizontalMargin,
                  ),
                  color: GovernanceColors.outlineVariant,
                ),
                TextButton(
                  onPressed: onPlaceholder,
                  style: TextButton.styleFrom(
                    foregroundColor: GovernanceColors.onSurfaceVariant,
                    padding: GovernanceInsets.textButton,
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text('Workspaces', style: tt.labelLarge),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: onPlaceholder,
                  style: FilledButton.styleFrom(
                    backgroundColor: GovernanceColors.primary,
                    foregroundColor: GovernanceColors.onPrimary,
                    padding: GovernanceInsets.primaryTopBarButton,
                    textStyle: tt.labelLarge,
                  ),
                  child: const Text('Import Project'),
                ),
                const SizedBox(
                  width: GovernanceDimensions.afterImportButtonGap,
                ),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.settings_outlined,
                    size: GovernanceDimensions.chromeIconSize,
                  ),
                  color: GovernanceColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.notifications_none_outlined,
                    size: GovernanceDimensions.chromeIconSize,
                  ),
                  color: GovernanceColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.account_circle_outlined,
                    size: GovernanceDimensions.chromeIconSize,
                  ),
                  color: GovernanceColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
