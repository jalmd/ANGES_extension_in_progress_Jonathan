import sys
import time
import re

from collections import defaultdict

from data_structures import markers
from data_structures import intervals
from data_structures import genomes
from data_structures import comparisons

import optimization
import assembly

from c1p_files import process_c1p
    

def strtime():
    """
    Function to format time to string
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
#enddef

class MasterMarkers:
    """
    Parse and solve markers info
    """
    def __init___(self):
        self.hom_fams_file_stream = None
        self.pairs_file_stream = None
    #enddef

    def setInputStreams(self, species_tree_dir, hom_fam_dir):
        try:
            self.pairs_file_stream = open(species_tree_dir, 'r')
        except IOError:
            log.write( "{}  ERROR (master.py) - could not open pairs file: {}\n"
                       .format(strtime(), self.io_dict["species_tree"]))
            sys.exit()
        
        try:
            self.hom_fams_file_stream = open(hom_fam_dir, 'r')
        except IOError:
            log.write( "{}  ERROR (master.py) - could not open homologous families file: {}\n"
                       .format(strtime(), self.io_dict["homologous_families"]))
            sys.exit()
    #enddef

    def parseSpeciesPairs(self, species_set, species_tree_dir, log):
        """
        Populating the species_pairs list
        """
        line_number = 1
        species_pairs = []
        for pair in self.pairs_file_stream:
        # Assume format of "<species1> <species2>", respect comments
            pair = pair.strip()
            pair = pair.split()
            if pair[0][0] != "#":
                if len( pair ) == 2:
                    if pair[0] not in species_set:
                        print("Semantic Error at line {} (file: {}): '{}'\n\tInvalid species '{}'. Not listed in the Homologous Families file\n"
                                .format(line_number,species_tree_dir, pair[0]+' '+pair[1],pair[0]))
                    elif pair[1] not in species_set:
                        print("Semantic Error at line {} (file: {}): '{}'\n\tInvalid species '{}'. Not listed in the Homologous Families file\n"
                                .format(line_number,species_tree_dir, pair[0]+' '+pair[1],pair[1]))
                    else:
                        species_pairs.append( pair )
                else:
                    print("Syntatic Error at line {} (file: {})\n\tInvalid number of species. Each line must have only one pair of species\n"
                                .format(line_number,species_tree_dir))
            line_number = line_number + 1
        self.pairs_file_stream.close()
        log.write( "{}  Read {} species pairs.\n"
                   .format(strtime(), len(species_pairs)))
        log.flush()

        return species_pairs
    #enddef

    # reads hom. families from a file
    # file_name - str: the name of the file to read from
    # hom_fam_list - list of HomFam: the list to add to (Default = [])
    # Return - list of HomFam: the list of hom. familes read
    def parseHomFamilies(self, hom_fam_dir, log):
        """
        Populates hom_fam_list
        """
        hom_fam_list = []
        line_number = 1
        line = self.hom_fams_file_stream.readline()
        while len(line) > 0:
            trunc_line = line.strip()

            if len(trunc_line) > 0:
                if trunc_line[0] == '>':
                    # read first hom. family
                    hom_fam, line = markers.HomFam.from_file(self.hom_fams_file_stream, trunc_line, line_number, hom_fam_dir)
                    if hom_fam != None:
                        hom_fam_list.append(hom_fam)
                    #endif

                    # read the rest of the hom. families
                    while len(line) > 0:
                        hom_fam, line = markers.HomFam.from_file(self.hom_fams_file_stream, line, line_number, hom_fam_dir)
                        if hom_fam != None:
                            hom_fam_list.append(hom_fam)
                        #endif
                    #endwhile
                else:
                    line = self.hom_fams_file_stream.readline()
                    line_number = line_number + 1
                #endif
            else:
                line = self.hom_fams_file_stream.readline()
                line_number = line_number + 1
            #endif
        #endif

        self.hom_fams_file_stream.close()

        log.write( "{}  Read homologous families from file.\n"
               .format( strtime() ) )
        log.flush()

        return hom_fam_list
    #enddef

    def doubleMarkers(self, hom_fam_list):
        return genomes.double_oriented_markers(hom_fam_list)
    #enddef

    def getOverlappingPairs(self, hom_fam_list, log):
        """
        getOverlappingPairs: receives a list of hom_fams and returns a list of overlapping pairs (each pair is a tuple containing two Locus)
        hom_fams - HomFam: list of objects from HomFam class
        """
        #import pdb; pdb.set_trace()
        loci_dict = defaultdict(list)
        overlapping_pairs_list = []

        for hom_fam_index, marker_family in enumerate(hom_fam_list):
            for locus_index, locus in enumerate(marker_family.loci):
               loci_dict[locus.species].append((hom_fam_index, locus_index))
            #endfor
        #endfor
        for species, species_indexes in loci_dict.items():
            # species name and a list of tuples with (hom_fam_index, locus_index)
            # hom_fam_index => access to hom_fam ID and loci list
            #print (species, species_indexes)
            i = 1
            locus1 = hom_fam_list[species_indexes[0][0]].loci[species_indexes[0][1]]
            while i < len(species_indexes):
                locus2 = hom_fam_list[species_indexes[i][0]].loci[species_indexes[i][1]]
                #print (locus1, locus2)
                is_overlapping_pair = locus1.overlappingPairs(locus2)
                if is_overlapping_pair:
                    overlapping_pairs_list.append(is_overlapping_pair)
                #endif
                i = i + 1
            #endwhile
        #endfor
        log.write("{}  {} overlapping pairs have been found.\n"
                    .format(strtime(), len(overlapping_pairs_list)))
        return overlapping_pairs_list
    #enddef

    def filterByID(self, id_list, hom_fam_list, log):
        """ 
        filterByID: Receives a list of IDs and remove them from the main markers list
        Returns a list 
        hom_fams - HomFam: list of HomFam
        ids - int: list of IDs to be removed from the hom_fams list
        """
        id_list = []
        filtered_list = filter(lambda fam: int(fam.id) not in id_list, hom_fam_list)
        for hom_fam in filtered_list:
            id_list.append(int(hom_fam.id))
        log.write( "{}  IDs {} filtred from homologous families list.\n"
                .format(strtime(), id_list))
        return filtered_list
    #enddef

    def filterByCopyNumber(self, copy_number_threshold, hom_fam_list, log):
        """
        filterByCopyNumber: receives a threshold and filter the main markers list by comparing the 
        copy_number with the threshold (if copy_number > threshold, remove from the list).
        Returns a list without the filtered markers.
        hom_fams - HomFam: List of markers
        theshold - int: filter using the threshold (filter if the copy_number is > threshold)
        """
        filtered_list = filter(lambda fam: fam.copy_number <= copy_number_threshold, hom_fam_list)
        filtered_quant = len(hom_fam_list) - len(filtered_list)
        log.write("{}  Filtered {} homologous families with Copy Number greater than {}.\n"
                    .format(strtime(), filtered_quant, copy_number_threshold ))
        return filtered_list
     #enddef

    def isCopyNumGreaterThanOne(self, hom_fam_list):
        filtered_list = filter(lambda fam: fam.copy_number <= 1, hom_fam_list)
        filtered_quant = len(hom_fam_list) - len(filtered_list)

        if filtered_quant != 0:
            return True
        else:
            return False
 
    def closePairsFile(self):
        self.pairs_file_stream.close()
    #enddef

    def closeHomFamsFile(self):
        self.hom_fams_file_stream.close()
    #enddef

class MasterAdjacencies:
    def __init__(self):
        self.adjacencies = intervals.IntervalDict()
        self.realizable_adjacencies = intervals.IntervalDict()
        self.discarded_adjacencies = intervals.IntervalDict()
        self.repeat_cluster = []
        self.repeat_cluster_int = []
    #enddef

    def getAdjacencies(self):
        return self.adjacencies
    #enddef

    def getRealizableAdjacencies(self):
        return self.realizable_adjacencies
    #enddef

    def getDiscardedAdjacencies(self):
        return self.discarded_adjacencies
    #enddef

    def getRepeatClusterList(self):
        return self.repeat_cluster

    def getRepeatClusterListInt(self):
        return self.repeat_cluster_int

    def solveAdjacencies(self, species_pairs, gens, output_directory, log, all_match):
        for pair in species_pairs:
            new_adjacencies = comparisons.find_adjacencies( gens[ pair[0] ],
                                                            gens[ pair[1] ], all_match)
            comparisons.add_intervals( self.adjacencies, new_adjacencies )
        comparisons.set_interval_weights( self.adjacencies )
        log.write( "{}  Found {} adjacencies with total weight of {}.\n"
                   .format( strtime(),
                      len( self.adjacencies ),
                      self.adjacencies.total_weight ) )
        log.flush()
        intervals.write_intervals(log, self.adjacencies, output_directory + "/adjacencies")
    #enddef

    def selectMaxAdjacencies(self, hom_fam_list, output_directory, log):
        self.realizable_adjacencies, self.repeat_cluster, self.repeat_cluster_int = optimization.opt_adjacencies(hom_fam_list, self.adjacencies)
        intervals.write_intervals(log, self.realizable_adjacencies, 
                         output_directory + "/realizable_adjacencies",
                        )
        log.write( "{}  Found {} realizable adjacencies with total weight of {}.\n"
               .format(strtime(),len(self.realizable_adjacencies), self.realizable_adjacencies.total_weight ) )
        log.write( "{}  Found {} repeat clusters.\n"
                .format(strtime(), len(self.repeat_cluster)))
        log.flush()
    #enddef

    def trackDiscardedAdjacencies(self, output_directory, log):
        for adj in self.adjacencies.itervalues():
            if not adj.marker_ids in self.realizable_adjacencies:
                self.discarded_adjacencies.add( adj )
        intervals.write_intervals(log, self.discarded_adjacencies, output_directory + "/discarded_adjacencies")
    #enddef
#endclass

class MasterRSI:
    def __init__(self):
        self.RSIs = intervals.IntervalDict()
        self.realizable_RSIs = intervals.IntervalDict()
        self.discarded_RSIs = intervals.IntervalDict()
    #enddef

    def getRSIs(self):
        return self.RSIs
    #enddef

    def getRealizableRSIs(self):
        return self.realizable_RSIs
    #enddef

    def getDiscardedRSIs(self):
        return self.discarded_RSIs
    #enddef

    def solveRSIs(self, species_pairs, gens, output_directory, log, all_match):
        for pair in species_pairs:
            new_RSIs = comparisons.find_RSIs(gens[ pair[0] ], gens[ pair[1] ], all_match)
            comparisons.add_intervals( self.RSIs, new_RSIs )
        comparisons.set_interval_weights( self.RSIs )
        log.write( "{}  Found {} repeat spanning intervals with total weight of"
        " {}.\n" .format( strtime(), len( self.RSIs ), self.RSIs.total_weight ) )
        log.flush()
        intervals.write_intervals(log, self.RSIs, output_directory + "/RSIs")
    #enddef
    
    def selectMaxRSIs(self, hom_fam_list, realizable_adjacencies, output_directory, log, debug):
        self.realizable_RSIs = optimization.opt_RSIs_greedy(
            hom_fam_list,
            realizable_adjacencies, 
            self.RSIs,
            "mixed",
            debug,
            )
        intervals.write_intervals(log, self.realizable_RSIs, output_directory + "/realizable_RSIs")
        log.write( "{}  Found {} realizable repeat spanning intervals with total weight of {}.\n"
                   .format(
                    strtime(),
                    len(self.realizable_RSIs ),
                    self.realizable_RSIs.total_weight 
                    )
                )
        log.flush()
    #enddef
    
    def trackDiscardedRSIs(self, output_directory, log):
        for RSI in self.RSIs.itervalues():
            if not RSI.marker_ids in self.realizable_RSIs:
                self.discarded_RSIs.add( RSI )
        intervals.write_intervals(log, self.discarded_RSIs, output_directory + "/discarded_RSIs")
    #enddef
#endclass

class MasterGenConstruction:
    def __init__(self): #deal with adjacencies and genome construction
        self.RSI = MasterRSI()
        self.adj = MasterAdjacencies()
        self.ancestor_name = "ANCESTOR"
        self.ancestor_hom_fams = []
        self.gens = {}
        self.RSI_strings = []
    #enddef

    def getGenomes(self):
        return self.gens
    #enddef

    def getAdjacencies(self):
        return self.adj

    # writes hom. families to a file
    # file_name - str: the name of the file to write to
    # hom_fam_list - list of HomFam: the list to write (Default = [])
    def writeAncestorHomFams(self,file_name):
        file_stream = open(file_name, 'w')

        for hom_fam in self.ancestor_hom_fams:
            hom_fam.to_file( file_stream )
            file_stream.write("\n")
            file_stream.flush()
        #endif

        file_stream.close()
    #enddef

    def constructGenomes(self, species_pairs, hom_fam_list, log):
        self.gens = genomes.get_genomes(
            hom_fam_list,
            list( set( species for pair in species_pairs for species in pair ) ),
            )
        log.write( "{}  Constructed genomes of {} species.\n" 
                        .format( strtime(), len( self.gens ) ) )
        log.flush()
    #enddef

    def dealWithAdjPhase(self, species_pairs, hom_fam_list, output_directory, log, debug, all_match):
        # For each pair of species, compare the species to find adjacencies.
        self.adj.solveAdjacencies(species_pairs, self.gens, output_directory, log, all_match)
        # how many times species pairs 

    def dealWithIntervalsPhase(self, species_pairs, hom_fam_list, output_directory, log, debug, all_match):
        # Do the same for repeat spanning intervals
        self.RSI.solveRSIs(species_pairs, self.gens, output_directory, log, all_match)

        # Select maximal subsets of adjacencies that are realizable.
        self.adj.selectMaxAdjacencies(hom_fam_list, output_directory, log)

        # Keep track of adjacencies that have been discarded.
        self.adj.trackDiscardedAdjacencies(output_directory, log)

        # Select maximal subsets of RSIs that are realizable.
        self.RSI.selectMaxRSIs(hom_fam_list, self.adj.realizable_adjacencies, output_directory, log, debug)

        # Keopep track of RSIs that have been discarded.
        self.RSI.trackDiscardedRSIs(output_directory, log)
    #enddef


    def checkAncestralAdjacencies(self, ancestor_genome, adj_str_list, RC_adjacencies):

        ancestor_adjacencies = []
        for chrom_id, chrom in ancestor_genome.chromosomes.iteritems():
            index = 0
            car = ""
            while index < len(chrom):
                car = car + str(chrom[index].id) + " "
                # print car
                found = False
                if (index+1) < len(chrom):
                    save_pair = []
                    save_pair.append(int(chrom[index].id))
                    save_pair.append(int(chrom[index+1].id))
                    save_pair.sort()
                    if save_pair in adj_str_list or save_pair in RC_adjacencies:
                        # found adjacency in adjacencies
                        ancestor_adjacencies.append(save_pair)
                        found = True
                else:
                    found = True

                if not found:
                    print "****** not found adjacency"
                    print save_pair
                    print car + str(chrom[index+1].id)
                    print "*****************************"
                index = index + 1

        for adj_pair in adj_str_list:
            if adj_pair not in ancestor_adjacencies or adj_pair in RC_adjacencies:
                print "***********adjacency in realizable_adjacencies not found in ancestor_genome adjacencies"
                print adj_pair

                
    def dealWithConstructionPhase(self, hom_fam_list, output_directory, log):
        self.ancestor_hom_fams = assembly.assemble(
            hom_fam_list,
            self.adj.realizable_adjacencies,
            self.RSI.realizable_RSIs,
            self.ancestor_name,
            )
        self.writeAncestorHomFams(
            output_directory + "/ancestor_hom_fams",
            )
        # To order the hom_fams in chromosomes, create a Genome object with
        # the new hom_fams.
        self.ancestor_genomes = genomes.get_genomes( 
            self.ancestor_hom_fams,
            [ self.ancestor_name ]
            )
        ancestor_genome = next( self.ancestor_genomes.itervalues() )
        
        # Create adjacencies list using an easier format to do the checkings
        i = 0
        adj_str_list = []
        adj_doubled_list = []
        for key in self.adj.realizable_adjacencies.endpoints.keys():
            for adj_pair in self.adj.realizable_adjacencies.endpoints[key]:
                save_pair = []
                save_pair.append(int(adj_pair[0][:-2]))
                save_pair.append(int(adj_pair[1][:-2]))
                save_pair.sort()
                if save_pair not in adj_str_list:
                    adj_str_list.append(save_pair)

                save_pair_str = []
                save_pair_str.append(adj_pair[0])
                save_pair_str.append(adj_pair[1])
                adj_doubled_list.append(save_pair_str)
            i = i + 1

        # Get the len of the greater RSI
        RSI_no_doubling = []
        max_RSI = 0
        for index, markers in enumerate(self.RSI.realizable_RSIs.itervalues()):
            RSI_no_doubling = [self.remove_head_tail(s) for s in markers.marker_ids]
            self.RSI_strings.append(" ".join(self.remove_duplicates(RSI_no_doubling)))
            if len(RSI_no_doubling) > max_RSI:
                max_RSI = len(self.remove_duplicates(RSI_no_doubling))

        # Edit the ancestral genome (check RC's and RSI's and if is circular or not)
        try:
            genome_output = open( output_directory + "/ancestor_genome", 'w' )
            genome_output.write( ">" + self.ancestor_name)
            
            # DealWith RC's
            for index, rc in enumerate(self.adj.getRepeatClusterList()):
                genome_output.write("\n#RC " + str(index+1) + "\n" + rc)
            print (self.adj.getRepeatClusterListInt())
            genome_output.write("\n")

            # DealWith CAR's
            RC_adjacencies = []
            CAR_total_list = []
            CAR_string_aux = ""
            for chrom_id, chrom in ancestor_genome.chromosomes.iteritems(): # Chrom = CARs
                CAR_string = ""
                index = 0
                previous_position = []
                while index < len(chrom):
                    flag = False
                    for index_rc, rc in enumerate(self.adj.getRepeatClusterListInt()):
                        if int(chrom[index].id) in rc:
                            flag = True
                            idx_rc = str(index_rc+1)

                    old_len = len(CAR_string)
                    CAR_string = CAR_string + str(chrom[index].id) + " "
                    new_len = len(CAR_string)
                    rc_len = new_len - old_len
                    if flag: # check if is RSI
                        i = 0
                        chrom_index = index + 1
                        CAR_string_aux = CAR_string
                        while i < max_RSI and chrom_index < len(chrom):
                            CAR_string_aux = CAR_string_aux + str(chrom[chrom_index].id) + " "
                            chrom_index = chrom_index + 1
                            i = i + 1
                        found_rsi = False
                        for rsi_unit in self.RSI_strings:
                            position = [m.start() for m in re.finditer(rsi_unit, CAR_string_aux)]
                            if position and position not in previous_position :
                                previous_position.append([m.start() for m in re.finditer(rsi_unit, CAR_string_aux)])
                                found_rsi = True
                                rsi_found = rsi_unit
                        if not found_rsi:
                            CAR_lst_int = [int(x) for x in CAR_string[:-1].split(" ")]
                            CAR_adj_pair = []
                            CAR_adj_pair.append(CAR_lst_int[len(CAR_lst_int)-2])
                            CAR_adj_pair.append(CAR_lst_int[len(CAR_lst_int)-1])
                            CAR_adj_pair.sort()
                            RC_adjacencies.append(CAR_adj_pair)
                            CAR_string = CAR_string[:-rc_len] + "RC" + idx_rc + " "
                            break
                        else: # found RSI
                            cut = CAR_string[1::-1].find(" ") 
                            CAR_string = CAR_string[:-rc_len-cut] + rsi_found + " "
                            index = index + max_RSI
                    else:
                        last_marker_id = chrom[index].id
                    index = index + 1
                
                # Check if is circular
                marker_pair = []
                marker_pair.append(chrom[0].id + "_h")
                marker_pair.append(last_marker_id + "_t")
                marker_pair2 = []
                marker_pair2.append(chrom[0].id + "_t")
                marker_pair2.append(last_marker_id + "_h")
                if marker_pair in adj_doubled_list or marker_pair2 in adj_doubled_list:
                    CAR_string = "_C " + CAR_string + "C_"
                else:
                    CAR_string = "_Q " + CAR_string + "Q_"

                CAR_total_list.append(CAR_string)

        except IOError:
            loglog.write( "{}  ERROR (master.py) - could not write ancestor genome to " "file: {}\n"
                            .format(strtime(), output_directory + "/ancestor_genome" ) )
            sys.exit()

        log.write( "{}  Assembled the ancestral genome, found a total of {} CARs and {} RCs.\n"
                   .format(strtime(), len(ancestor_genome.chromosomes), len(self.adj.getRepeatClusterList()) ) )
        log.write( "{}  Done.\n".format(strtime()) )

        # Write the ancestral genome (CARs)
        genome_output.write("\n")
        CAR_total_list.sort(key = len, reverse = True)
        for idx_car,CAR in enumerate(CAR_total_list):
            print_CAR = ("#CAR " + str(idx_car+1) + "\n" + CAR + "\n")
            genome_output.write(print_CAR)

        # Check if the adjacencies in Ancestral genome adjacencies are in the Realizable adjacencies (report when not in)
        # Also check if the adjacencies in realizable adjacencies are in the ancestral genome (report when not in)
        self.checkAncestralAdjacencies(ancestor_genome, adj_str_list, RC_adjacencies)

    #enddef
    def remove_head_tail(self, s):
        return s[:-2]

    def remove_duplicates(self,li):
        my_set = set()
        res = []
        for e in li:
            if e not in my_set:
                res.append(e)
                my_set.add(e)
        #
        return res
#endclass

class MasterScript:
    """
    MasterScript Class: coordinates the main process using some aux classes
    A MasterScript object must have all the most important information regarding homologous families and spcecies pairs and this object will coordinate all phases 
    io_dict - {string : string}: dictionary that will be populated based on the configuration.conf file 
                                this dictionary will have all the IO directories
    markers_param_dict - {string : int} or {string : [int]}: also will be populated based on the configuration.conf file (parse_markersPhase)
                                this dictionary will have all the markers running parameters (different execution modes)
    log - filestream: stream for the log file
    debug - filestream: stream for the debug file
    species_pairs: list of species_pairs -> populated based on the species_pairs file, during the parse_markersPhase
    hom_fam_list: list of homologous families -> populated based on the hom_fams_file, during the parse_markersPhase
    overlapped_pairs_list: list of overlapping pairs, populated based on the hom_fam_list, during the parse_markersPhase
    genome_construction_obj - MasterGenConstruction class object -> this object deal with adjacenciesPhase and genomeConstructionPhase and 
                                                                    has information regarding gens, adjacencies, ancestral genomes (including methods to manipulate these information)  
    """
    def __init__(self):
        self.config_file_directory = ""
        self.io_dict = {}
        self.markers_param_dict = {}
        self.run_param_dict = {}

        self.log = None
        self.debug = None
    
        self.species_pairs = []
        self.hom_fam_list = []
        self.species_set = set()
        self.overlapping_pairs_list = []
        self.genome_construction_obj = MasterGenConstruction()

        self.adjacencies = {}
        self.realizable_adjacencies = {}
        self.discarded_adjacencies = {}

        self.received_acs = False
        self.doC1P = False
        self.doMWM = False
    #enddef

    def setOutputStreams(self):
        try:
            self.log = open(self.io_dict["output_directory"] + "/log", 'w' )
        except IOError:
            print ( "{}  ERROR (master.py) - could not open log file: {}"
                    .format(strtime(), self.io_dict["output_directory"] + "/log" ) )
            sys.exit()
        if __debug__:
            try:
                self.debug = open(self.io_dict["output_directory"] + "/debug", 'w' )
            except IOError:
                log.write( "ERROR (master.py) - could not open debug file {}"
                           .format(self.io_dict["output_directory"] + "/debug"))
    #enddef

    def setConfigParams(self, config_file, len_arguments):
        """
        Function to read the configuration file and return all the interpreted information
        Arguments:
        config_file - string: configuration file directory
        len_arguments - int: arguments length

        Returns: homologous families file directory
                 species tree file directory 
                 output directory
                 markers parameters (markers_doubled - int, markers_unique - int, markers_universal - int,
                                     markers_overlap - int, filter_copy_number - int, filter_by_id - list of int)
                where homologous families, species tree and output are keys for a dictionary and their respective 
                directories are the values for these keys;
                markers parameters is a dictionary using markers_doubled, ..., filter_by_id as keys and the values
                are the parameter values of each parameter (informed in the configuration file)
        """

        if len_arguments != 2:
            print ( "{}  ERROR (master.py -> process.py) - script called with incorrect number "
                     "of arguments.".format(strtime()))
            sys.exit()
        #endif
        config = {}
        try:
            execfile(config_file, config)
        except IOError:
            print("{}  ERROR (master.py -> process.py) - could not open configuration file: {}\n"
                    .format(strtime(),config_file))
            sys.exit()
        
        #collect the information from config file
        self.io_dict["homologous_families"]           = config["homologous_families"]
        self.io_dict["species_tree"]                  = config["species_tree"]
        self.io_dict["output_directory"]              = config["output_directory"]
        self.io_dict["acs_file"]                     = config["acs_file"]

        self.markers_param_dict["markers_doubled"]    = config["markers_doubled"]
        self.markers_param_dict["markers_unique"]     = config["markers_unique"]
        self.markers_param_dict["markers_universal"]  = config["markers_universal"]
        self.markers_param_dict["markers_overlap"]    = config["markers_overlap"]
        self.markers_param_dict["filter_copy_number"] = config["filter_copy_number"]
        self.markers_param_dict["filter_by_id"]       = config["filter_by_id"]

        self.run_param_dict["all_match"]            = config["all_match"]

        self.debug = config["debug"]

        self.config_file_directory = config_file
        if config["acs_file"] != "":
            self.received_acs = True
        
        config.clear()
        self.setOutputStreams() #set Log and Debug

    #enddef

    def receivedAcsFile(self):
        return self.received_acs

    def parse_markersPhase(self):
        """
        Deal with everything realated to input (configuration, markers and species pairs) in order to take information from these files

        """
        # MasterMarkers class: methods used in order to deal with input files and take information from them (populate the species_pairs list and hom_fam_list)
        markers_phase_obj = MasterMarkers() 
        markers_phase_obj.setInputStreams(self.io_dict["species_tree"],self.io_dict["homologous_families"]) #set pairs file stream and hom fams file stream
        # Parse the hom fams file.
        self.hom_fam_list = markers_phase_obj.parseHomFamilies(self.io_dict["homologous_families"], self.log)
        self.getSpeciesList()
        # Parse the species pair file, put result in list.
        self.species_pairs = markers_phase_obj.parseSpeciesPairs(self.species_set, self.io_dict["species_tree"], self.log)
        # hom_fam_list and species_pairs list are now populated

        # Filter by ID
        if self.markers_param_dict["filter_by_id"]:
            self.hom_fam_list = markers_phase_obj.filterByID(self.markers_param_dict["filter_by_id"], self.hom_fam_list, self.log)

        # Filter by Copy Number
        if self.markers_param_dict["filter_copy_number"] != 0:
            print "filtering"
            self.hom_fam_list = markers_phase_obj.filterByCopyNumber(self.markers_param_dict["filter_copy_number"], self.hom_fam_list, self.log)

        #Get all overlapped pairs
        if self.markers_param_dict["markers_overlap"] == 1:
            self.overlapping_pairs_list = markers_phase_obj.getOverlappingPairs(self.hom_fam_list, self.log)
        
        # Since the markers are all oriented, double them.
        self.hom_fam_list = markers_phase_obj.doubleMarkers(self.hom_fam_list)

        # if there is some marker with copy number greater than one, do MWM
        # if all copy numbers are one, do C1P
        if markers_phase_obj.isCopyNumGreaterThanOne(self.hom_fam_list):
            self.doC1P = False
            self.doMWM = True
        else:
            self.doC1P = True
            self.doMWM = False

        del markers_phase_obj
    #enddef

    def adjacenciesPhase(self):
        # Genome construction
        self.genome_construction_obj.constructGenomes(self.species_pairs, self.hom_fam_list, self.log)
        self.genome_construction_obj.dealWithAdjPhase(self.species_pairs, self.hom_fam_list, self.io_dict["output_directory"], self.log, self.debug, self.run_param_dict["all_match"])
    #enddef

    def intervalsPhase(self):
        self.genome_construction_obj.dealWithIntervalsPhase(self.species_pairs, self.hom_fam_list, self.io_dict["output_directory"], self.log, self.debug, self.run_param_dict["all_match"])

    def c1pPhase(self):
        c1p_obj = process_c1p.MasterC1P()

        adjacencies = self.genome_construction_obj.getAdjacencies().getAdjacencies()
        realizable_adjacencies = self.genome_construction_obj.getAdjacencies().getRealizableAdjacencies()
        discarded_adjacencies = self.genome_construction_obj.getAdjacencies().getDiscardedAdjacencies()

        c1p_obj.setConfigParams(self.config_file_directory,adjacencies,realizable_adjacencies,discarded_adjacencies)
        c1p_obj.run()

    def genomeConstructionPhase(self):
        self.genome_construction_obj.dealWithConstructionPhase(self.hom_fam_list, self.io_dict["output_directory"], self.log)
    #enddef

    # finds a HomFam in a list given a marker id
    # hom_fam_list - list of HomFam: the list to look in
    # marker_id - str: the marker_id to look for
    # Return - HomFam: the hom. family with marker id, marker_id
    def findHomFam(marker_id):
        # Filter the list
        matches = filter( lambda hom_fam: hom_fam.id == marker_id, self.hom_fam_list )
        # Return first element of the list
        if matches:
            return matches[0]
        else:
            return None
    #enddef

    def closeLogFile(self):
        self.log.close()
    #enddef

    def closeDebugFile(self):
        self.log.close()
    #enddef

    def closeAllFiles(self):
        self.closeLogFile()
        self.closeDebugFile()
    #enddef

    def doC1PorNot(self):
        return self.doC1P # if false, do MWM

    def getSpeciesList(self):
        for marker_family in self.hom_fam_list:
            for locus_index,locus in enumerate(marker_family.loci):
                self.species_set.add(marker_family.loci[locus_index].species)

    def getIODictionary(self):
        return self.io_dict, self.markers_param_dict
    #enddef

    def getFileStreams(self):
        return self.log, self.debug
    #enddef

    def getSpeciesPairs(self):
        return self.species_pairs
    #enddef

    def getHomFamList(self):
        return self.hom_fam_list
    #enddef
#endclass