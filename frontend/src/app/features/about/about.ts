import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { VERIFY_OPTIONS } from '../verification/verify-facts/verify-options';

@Component({
  selector: 'app-about',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './about.html',
  styleUrls: ['./about.scss'],
})
export class AboutComponent {
  readonly options = VERIFY_OPTIONS;

  readonly steps = [
    { title: 'Submit', text: 'Send a news story with an image, a news story with its claimed source, or a photocard.' },
    { title: 'Initial result', text: 'Model prediction or automatic evaluation gives a preliminary finding within minutes.' },
    { title: 'Expert review', text: 'Independent experts examine the evidence and vote on the claim.' },
    { title: 'Final verdict', text: 'Votes are weighted by each expert\'s track record and the final verdict is published.' },
  ];

  readonly verdicts = [
    { label: 'Real', cls: 'badge-true', text: 'The claim is accurate.' },
    { label: 'Fake', cls: 'badge-false', text: 'The claim is false.' },
    { label: 'Altered', cls: 'badge-partial', text: 'The original content was materially changed.' },
    { label: 'Misleading', cls: 'badge-partial', text: 'The claim gives a misleading impression.' },
  ];

  readonly principles = [
    { title: 'Evidence first', text: 'Every finding is tied to the source article, the image or the card that was checked.' },
    { title: 'Human judgement', text: 'Automated results are never final. Experts decide every verdict.' },
    { title: 'Accountable reviewers', text: 'Expert credibility is earned from how often their votes match final verdicts.' },
    { title: 'Open results', text: 'Finalised fact checks are public in Fact Explorer for anyone to read and share.' },
  ];
}
