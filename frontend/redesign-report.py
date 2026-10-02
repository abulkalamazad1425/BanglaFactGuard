from pathlib import Path
p=Path('frontend/src/app/shared/components/verification-report/verification-report.component.ts')
s=p.read_text(encoding='utf-8-sig'); start=s.index('  template: `',s.index("selector: 'app-verification-report'")); end=s.index('\n})',start)
s=s[:start]+"  templateUrl: './verification-report.component.html',"+s[end:]
s=s.replace('imports: [DatePipe, NgClass, VerdictBadgeComponent, ResultChecksComponent],','imports: [DatePipe, VerdictBadgeComponent, ResultChecksComponent, ResultScoresComponent],')
s=s.replace('@Input({ required: true }) r!: VerificationResponse;', '@Input({ required: true }) r!: VerificationResponse;\n  @Input() reviewer = false;')
s=s.replace('<h4>🔍 Alteration checks</h4>','<h4>Recorded comparison checks</h4>')
p.write_text(s,encoding='utf-8')
