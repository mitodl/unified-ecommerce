# Generated by Django 4.2.16 on 2024-11-21 14:54

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0012_company_discount_transaction_number_and_more"),
    ]

    def create_companies_from_xpro(apps, scheme_editor):  # noqa: ARG002, N805
        """
        Create companies from the list of companies in the XPRO database.
        """
        COMPANY_NAMES = [
            "MIT Open Learning",
            "Aerojet Rocketdyne",
            "Ford Motor Company",
            "Boeing",
            "Whirlpool",
            "BOEING_NO_MATCH_VOUCHER",
            "Naval Air Warfare Center",
            "US Army",
            "Grundfos",
            "Stoneridge",
            "Excelitas Technologies Corp",
            "General Atomics Aeronautical",
            "Naval Undersea Warfare CTR",
            "GENERAL MOTORS TEP",
            "AECOM Limited",
            "Pearson Education, Inc.",
            "Ontario Power Generation",
            "TATA Technologies",
            "BAE Systems",
            "US Army System Analysis Division",
            "NRL Stennis Space Center Military, Navy",
            "US Army ARDEC Picatinny",
            "Autodesk",
            "Accenture",
            "IBM",
            "how2se",
            "Yupana Inc",
            "Department of Veteran Affairs",
            "The School of Management Fribourg",
            "US ARMY - National Ground Intelligence Center",
            "Shell",
            "Boeing Defense Australia",
            "MIT Lincoln Laboratory",
            "Federal Bureau of Investigation",
            "Army Pentagon",
            "GHSP",
            "Science and Engineering LLC",
            "Blue Origin",
            "MIT",
            "FEMA",
            "University of Luxembourg",
            "Elyah.io",
            "ReACT",
            "EdX",
            "Accenture Federal Services",
            "General Dynamics",
            "Diamond Light Source",
            "NATO",
            "Baker Hughes",
            "Jackson University",
            "Yara",
            "Ysleta Independent School District",
            "Frigel",
            "E-Ink",
            "Thermo King",
            "University of Florence",
            "Tuskegee University",
            "TRR Trygghetsradet",
            "Empacco",
            "Dynamic Controls",
            "Heller Measurements",
            "Raytheon Technologies",
            "DBML Group",
            "Ball Aerospace & Technologies Corporation",
            "CNH INDUSTRIAL",
            "US Navy",
            "University of the District of Columbia",
            "Irving Sh\u200bipping",
            "Bob Weiler",
            "UTC Learning",
            "Touch Education Technology",
            "Johnson Controls Hitachi Air Conditioning",
            "Mohamed Adel Aboelfotoh",
            "Lukasiewicz Research Network",
            "UNIVERSITE DU LUXEMBOURG",
            "Defense Intelligence Agency",
            "Aliena",
            "TU Delft",
            "CISR",
            "FFT",
            "Mitsubishi Aircraft Corporation",
            "Make3D Company Limited",
            "Fraunhofer",
            "Lemoyne-Owen College",
            "Stuttgart",
            "NFLPA",
            "Starline",
            "Ayna Analytics GmbH",
            "Carmeq",
            "Tusas",
            "Fsue Nami",
            "Institute of Space Science - NFLPR",
            "Politechnika",
            "Ford Europe",
            "Ford Mexico",
            "AUI",
            "Memic",
            "RIMAC Seguros",
            "Arrival",
            "Coskunos",
            "Deloitte",
            "ECA Group",
            "Navantia",
            "Leonardo",
            "Uganda Revenue Authority",
            "Roketsan",
            "Rolls-Royce",
            "Zendesk Ticket",
            "Khan Academy",
            "Silesian University of Technology",
            "ABN-AMRO Bank",
            "ESTIAN",
            "Intermind",
            "MIT Startup Exchange",
            "Draper",
            "POMI",
            "Tonal",
            "BMW AG",
            "Guild",
            "Bank of Brazil",
            "Oxford Instruments",
            "EMC Nord LLC.",
            "NASA",
            "Scandiweb",
            "Applied Materials Inc",
            "Abu Dhabi Music & Arts Foundation",
            "AM Aero",
            "Department of Defense",
            "Fujitsu",
            "Total E&P UK Limited",
            "Geisinger Health System",
            "Systelab Tech",
            "Ideationeng",
            "General Motors",
            "Osler DIagnostics Limited",
            "CCC",
            "Altran Innovacion SL",
            "Uppsala University",
            "BorgWarner",
            "Universidad de Deusto",
            "Lam Research Corporation",
            "Turkish Aerospace Industries",
            "Logitrade",
            "University of Essex",
            "Jacobs University",
            "Murray Industries",
            "Mahindra",
            "Tera Automation SRL",
            "Arizona Dept of Economic Security",
            "Instituto de Astrofisica de Canarias",
            "MM Karton",
            "Cal Poly Pomona",
            "Universidad Nebrija",
            "Metrica",
            "Global Foundries",
            "Air Force",
            "GMV Aerospace & Defense",
            "HP",
            "University of Zagreb",
            "Kalmar Solutions LLC",
            "Aselsan",
            "TMC Science and Technology",
            "ManTech International Corporation",
            "Northrop Grumman Sperry Marine",
            "Flextronics Instituto",
            "Rimac Automobili d.o.o.",
            "Project 3 Mobility",
            "Questum",
            "Eaton eMobility France",
            "Evi Technologies",
            "Dassault Systemes",
            "City and County of San Francisco",
            "Porsche Consulting",
            "Alpha Precision Group",
            "European Space Agency",
            "Vexels",
            "Universite Polytechnique Hauts-de-France",
            "Hakeem Isa",
            "Beckman Coulter",
            "Roketsan Missiles Inc",
            "North Carolina AT",
            "Northrop Grumman Corporation",
            "Impact Capital AM",
            "Universidad Rey Juan Carlos",
            "Stanley Black and Decker",
            "Ford Turkey",
            "FAA",
            "CERN",
            "University of Twente",
            "Associated Universities",
            "Liebherr Machines Bulle",
            "Novartis",
            "KUKA",
            "Equinix",
            "EIT Manufacturing",
            "Lockheed Martin",
            "Siemens Healthcare GmbH",
            "ThermoFisher",
            "Sartorius",
            "Nikola Motor Company",
            "Lucid Motors",
            "Expertis Decision",
            "OMI-POLO ESPAÑOL, S.A.",
            "DyeMansion NA Inc.",
            "Deacero",
            "INTERCONEXION",
            "ULB",
            "Platinion Srl",
            "SIG Sauer",
            "Visteon Electronics Bulgaria EOOD",
            "Trentino Sviluppo SPA",
            "MIT Media Lab",
            "ZEISS International",
            "DePuy Synthes",
            "Ecole Polytechnique - Laboratory of hydrodynamics",
            "PSDSARC",
            "Pratt & Whitney",
            "Vattenfall NV",
            "Smith Institute",
            "Logistics Management Institute",
            "Waterford Institute of Technology",
            "EduBroker sp. z o.o.",
            "Airbus Defence and Space",
            "Department of Rehabilitation",
            "RCDB",
            "Protolabs Ltd",
            "CMR Surgical",
            "Plexus Manufacturing SDN BHD",
            "Airgas USA, LLC",
            "University of Johannesburg",
            "General Electric",
            "Ammar Ahmad Qazi",
            "Marin",
            "Nestle",
            "Materialise",
            "Draeger",
            "LearnQuest",
            "BASF",
            "Cochlear",
            "Decathlon",
            "Lidl Magyarország Bt",
            "Prosegur",
            "Women in 3D Printing",
            "Ansys",
            "NIIT",
            "Instituto Nacional de Técnica Aeroespacial",
            "Schindler",
            "Leica",
            "Caulfield Industrial",
            "ASELSAN A.S",
            "Abhijit Chandra Roy",
            "Terna Energy",
            "Krishnamoorthy Karunakaran",
            "Ferrovial Spain",
            "Honeywell FMT",
            "CCP Games",
            "Hitachi",
            "Infosys",
            "AXPO",
            "Voiso Pte Ltd",
            "VulcanForms",
            "Smiths Detection",
            "Arlington Independent School District",
            "Sigma Technology",
            "Telespazio",
            "Freddie Mac",
            "Nexans",
            "ABB",
            "School of Mechanical Engineering, College of Engineering, Universiti Teknologi MARA",
            "Washington Metro Transit Authority",
            "Deacero SAPI de CV",
            "Innoviz",
            "Nova Systems",
            "Komatsu Mining Corp",
            "GE Aviation",
            "Amazon",
            "Ujima Med, Inc.",
            "Fatima Zahra",
            "Radiometer",
            "Elev8",
            "Roman Stefanov",
            "Queens University Belfast",
            "Crown",
            "Absa Bank",
            "CEIT BRTA",
            "TTI",
            "PureTech Health LLC",
            "GMR Group",
            "Instituto de Soldadura e Qualidade",
            "Royal New Zealand Air Force",
            "Anzen Aerospace Engineering SL",
            "Fabernovel",
            "HSBC",
            "WHU - Otto Beisheim School of Managment",
            "Trodo",
            "Institute of High Performance Computing",
            "Brooke Charter Schools",
            "Simplilearn",
            "VAAL",
            "Rivian",
            "ALBAIK Food Systems Company Ltd",
            "Nirvana Soft",
            "Enersys",
            "Amgen",
            "Sanlam",
            "Technology Innovation Institute",
            "ASM Technologies",
            "Bearing Point",
            "IO Consulting",
            "ADGM",
            "Banco Mizuho do Brasil SA",
            "United Nations Development Program",
            "INA",
            "Quantum OneHundred",
            "Hughes",
            "Engineering Do Brasil",
            "DO NOT USE",
            "HEAD Acoustics",
            "Lear Corporation Engineering Spain SLU",
            "Eink",
            "Adaptix",
            "Optos",
            "UCLouvain",
            "Andre Shahbazian",
            "University of Limerick",
            "BOEING_INTL_LEARNER",
            "Abu Dhabi Global Market Academy",
            "Banque De France",
            "Stellantis",
            "Essentium",
            "University of Sri Jayewardenepura",
            "Hensoldt",
            "Artion Medical",
            "OHB System AG",
            "FMI",
            "SAFT",
            "Robert Bosch USA",
            "Roltec Sp. z o.o.",
            "Mazda",
            "ASML",
            "Volocopter GmbH",
            "Islamic Financial Services Board",
            "Unveiled",
            "Sensata Technologies",
            "Ministry of Defence of Czech Republic",
            "Caris MPI, Inc., d/b/a Caris Life Sciences",
            "Cherokee Nation",
            "Council for Scientific and Industrial Research",
            "PACCAR Technical Center",
            "PACE",
            "Thales",
            "INAF",
            "Ariston",
            "B2C Learner",
            "LG-LHT Aircraft Solutions GmbH",
            "Gamax Laboratory Solutions Kft.",
            "North Carolina Agricultural and Technical State University",
            "TECHNISCHE UNIVERSITÄT WIEN",
            "Societe National",
            "Eyüp Polat",
            "Motive",
            "Halcon Systems LLC",
            "Colorado Dept of Labor",
            "Singapore University Of Technology & Design",
            "Mondelēz International",
            "Heliox BV",
            "Universidad Miguel Hernandez",
            "Madison College",
            "Vestas",
            "Edubookers",
            "Brascabos Componentes",
            "Complete Genomics",
            "Sony Corporation of America",
            "Generali Group",
            "John Deere",
            "Rheinmetall Technical Publications GmbH",
            "Autocount",
            "Egis Group",
            "Bauhaus-Universität Weimar",
            "Aselsan Group",
            "Dana",
            "Web B.V.",
            "Swedish Orphan Biovitrum",
            "PSITech",
            "Repsol",
            "Saint-Gobain Recherche",
            "Tractebel Engineering",
            "Collaborative Code",
            "Intalus",
            "Gore",
            "IBA SA",
            "Lus Kaos",
            "Hunt Valve Company",
            "GKN",
            "HorizonX",
            "Institute of Technology Bandung",
            "CGI Eesti AS",
            "Dept. of Chemistry, Faculty of Mathematics and Natural Sciences, Universitas Gadjah Mada, Indonesia",
            "Safran",
            "Luminor Bank AS Latvijas filiāle",
            "VDL ETS",
            "BEC Financial Technologies a.m.b.a",
            "Neusta",
            "Skylab",
            "Clinilab-Bekyras SA",
            "Mahidol University",
            "Warsaw University of Technology",
            "D-Orbit",
            "Bissell",
            "JAGUAR LAND ROVER LIMITED",
            "Saab Australia",
            "US Air Force",
            "HCLTech",
            "Peak",
            "Alpitronic SRL",
            "BAE Systems Nashua",
            "NTT DATA",
            "Department of National Defence",
            "BIS",
        ]

        CompanyModel = apps.get_model("payments", "Company")

        for company_name in COMPANY_NAMES:
            CompanyModel.objects.create(name=company_name)

    operations = [
        migrations.RunPython(create_companies_from_xpro),
    ]
