# https://www.kaggle.com/competitions/birdclef-2026/overview

# Overview
The goal of this competition is to develop machine learning frameworks capable of identifying understudied species within continuous audio data from Brazil's Pantanal wetlands. Successful solutions will help advance biodiversity monitoring in the last wild places on Earth.


# Description
How do you protect an ecosystem you can’t fully see? One way is to listen.

This competition involves building models that automatically identify wildlife species from their vocalizations in audio recordings collected across the Pantanal wetlands. This work will support more reliable biodiversity monitoring in one of the world’s most diverse and threatened ecosystems.

Understanding how ecological communities respond to environmental change and restoration efforts is a central challenge in conservation science. The Pantanal — a wetland spanning 150,000+ km² across Brazil and neighboring countries — is home to over 650 bird species plus countless other animals, yet much of it remains unmonitored. Seasonal flooding, wildfires, agricultural expansion, and climate change make regular fieldwork challenging.

# Goal of the Competition
Conventional biodiversity monitoring across vast, remote regions is expensive and logistically demanding. To help address these challenges, a growing network of 1,000 acoustic recorders is being deployed across the Pantanal, running continuously to capture wildlife sounds across different habitats and seasons. Continuous audio recording allows researchers to capture multi-species soundscapes over extended periods, providing a community-level perspective on biodiversity dynamics. But the sheer volume of audio is too large to review manually, and labeled species data is limited.

This competition focuses on the development of machine learning models that identify wildlife species from passive acoustic monitoring (PAM). Proposed approaches should work across different habitats, withstand the constraints of messy, field-collected data, and support evidence-based conservation decisions. Successful solutions will help advance biodiversity monitoring in the last wild places on Earth, including research initiatives in the Pantanal wetlands of Brazil.

Listening carefully, and at scale, may be one of the most effective tools available to protect this landscape.

# Timeline
March 11, 2026 - Start Date.

May 27, 2026 - Entry Deadline. You must accept the competition rules before this date to compete.

May 27, 2026 - Team Merger Deadline. This is the last day participants may join or merge teams.

June 3, 2026 - Final Submission Deadline.

All deadlines are at 11:59 PM UTC on the corresponding day unless otherwise noted. The competition organizers reserve the right to update the contest timeline if they deem it necessary.

# Evaluation
The evaluation metric for this contest is a version of macro-averaged ROC-AUC that skips classes that have no true positive labels.
[Example Notebook](competition_specification/birdclef-roc-auc.ipynb)

# Submission Format
For each row_id, you should predict the probability that a given species was present. There is one column per species. Each row covers a five-second window of audio.


# Code Requirements
This is a Code Competition

Submissions to this competition must be made through Notebooks. For the "Submit" button to be active after a commit, the following conditions must be met:

CPU Notebook <= 90 minutes run-time
GPU Notebook submissions are disabled. You can technically submit but will only have 1 minute of runtime.
Internet access disabled
Freely & publicly available external data is allowed, including pre-trained models
Submission file must be named submission.csv
Please see the Code Competition FAQ for more information on how to submit. And review the code debugging doc if you encounter submission errors.

# Acknowledgements
The development of the competition dataset was supported by the Bezos Earth Fund AI for Climate and Nature Grand Challenge.
https://www.bezosearthfund.org/news-and-insights/bezos-earth-fund-announces-30-million-in-ai-grand-challenge-awards

Compiling this extensive dataset was a major undertaking, and we are very thankful to the many domain experts who helped to collect and manually annotate the data for this competition. Specifically, we would like to thank (institutions and individual contributors in alphabetic order):

Chemnitz University of Technology: Stefan Kahl, Mario Lasseck, and Maximilian Eibl
https://www.tu-chemnitz.de/index.html.en

Google Deepmind: Tom Denton
https://deepmind.google//

iNaturalist: Grant van Horn
https://www.inaturalist.org/

Instituto Homem Pantaneiro: Wener Hugo Arruda Moreno
https://institutohomempantaneiro.org.br/

Instituto Nacional de Pesquisa do Pantanal (INPP): Carolline Zatta Fieker, Karl-L. Schuchmann, Kirk Thiago Pedroso Azevedo, Lucas Korzune Sampaio Teles, Marinez Isaac Marques and Matheus Gonçalves dos Reis
https://www.gov.br/inpp/en?set_language=en

K. Lisa Yang Center for Conservation Bioacoustics: Stefan Kahl, Larissa Sugai and Holger Klinck
https://www.birds.cornell.edu/ccb/

LifeCLEF: Alexis Joly and Henning Müller
https://www.ufms.br/

Sauá Consultoria Ambiental: Carolina Martins Garcia
https://www.sauaambiental.com.br/

Universidade Federal de Mato Grosso do Sul (UFMS): Alyson Vieira de Melo, Daiene Louveira Hokama Sousa, José Luiz Massao Moreira Sugai, João Emílio de Almeida Júnior, Liliana Piatti, Mariana Motti Barbosa, Matheus de Oliveira Neves, Priscila do Nascimento Lopes and Ryan Christopher Kridler
https://www.ufms.br/

Xeno-canto: Willem-Pier Vellinga, Bob Planqué
https://xeno-canto.org/

Photo Credits

Banner picture of a Hyacinth Macaw by Thomas Fuhrmann. Inset picture of a Jaguar by Leonardo Ramos.

# Citation
Stefan Kahl, Tom Denton, Larissa Sugai, Liliana Piatti, Ryan Holbrook, Holger Klinck, and Ashley Oldacre. BirdCLEF+ 2026. https://kaggle.com/competitions/birdclef-2026, 2026. Kaggle.