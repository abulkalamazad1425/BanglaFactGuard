import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

export interface FaqTopic {
  id: string;
  question: string;
}

/**
 * Frequently asked questions about how results are produced. The answers
 * describe the implemented behaviour (see the backend's
 * analysis/headline_comparison.py, analysis/body_similarity.py and
 * photocard/claim_extraction.py) and must be kept in step with it.
 */
@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './faq.html',
  styleUrls: ['./faq.scss'],
})
export class FaqComponent {
  readonly topics: FaqTopic[] = [
    { id: 'headline-alteration', question: 'What is Headline Alteration?' },
    {
      id: 'matched-altered',
      question: 'What do Exact Matched, Meaning Preserved and Altered mean?',
    },
    { id: 'source-not-found', question: 'What do “Found” and “Not found in claimed source” mean?' },
    { id: 'final-decision', question: 'Who makes the final decision?' },
    { id: 'body-scores', question: 'What are the body similarity scores?' },
    { id: 'score-range', question: 'How should I read a score?' },
    { id: 'not-a-verdict', question: 'Why are body scores not a verdict?' },
    { id: 'unavailable', question: 'When is a body score unavailable?' },
    { id: 'photocard', question: 'How is a photo card read?' },
    { id: 'date', question: 'How is the publication date checked?' },
  ];
}
