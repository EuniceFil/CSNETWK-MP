Need more than one devices

Syntax:
python3 profile.py Name

Verbose mode:
python profile.py Name --verbose

For the game: 
peers
ttinvite Bob@127.0.0.1 X
ttmove g0 POSITION

- In peers, both should be seen
- Position if it's from 0-8 

For profile picture:
Image should be in the same folder as the source code.

Work Distribution Matrix
| Task / Role | Filipino, Eunice Marble | Filipino, Audric Justin | Lazaro, Heisel Janine | Wee, Justine Erika |
| :--- | :---: | :---: | :---: | :---: |
| **Network Communication** | | | | |
| UDP Socket Setup | | Reviewer | Primary | Secondary |
| mDNS Discovery Integration | | Reviewer | Primary | Secondary |
| IP Address Logging | | Secondary | Primary | Reviewer |
| **Core Feature Implementation** | | | | |
| Core Messaging (POST, DM, LIKE, FOLLOW) | Primary | Reviewer | Secondary | |
| File Transfer (Offer, Chunk, ACK) | Reviewer | Primary | Reviewer | |
| Tic Tac Toe Game (with recovery) | Reviewer | Secondary | | Primary |
| Group Creation / Messaging | Primary | Reviewer | Primary | Secondary |
| Induced Packet Loss (Game & File) | | | Secondary | Reviewer |
| Acknowledgement / Retry | Secondary | Reviewer | Primary | |
| **UI & Logging** | | | | |
| Verbose Mode Support | Primary | | Secondary | Reviewer |
| Terminal Grid Display | Reviewer | | Secondary | Primary |
| Message Parsing & Debug Output | Secondary | Primary | | Reviewer |
| **Testing and Validation** | | | | |
| Inter-group Testing | Primary | Primary | | Secondary |
| Correct Parsing Validation | Primary | Reviewer | Secondary | |
| Token Expiry & IP Match | Secondary | | Primary | Reviewer |
| **Documentation & Coordination** | | | | |
| RFC & Project Report | | Reviewer | | Secondary |
| Milestone Tracking & Deliverables | Secondary | | Primary | Reviewer |
