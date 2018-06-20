import argparse
import copy
import datetime as dt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import ranklist
import sys
import time
from data_transform import read_data
from helper import *
from iForest import iForest
from LookOut import LookOut
from math import log
from matplotlib.backends.backend_pdf import PdfPages
from plot_functions import *
from structures import *
from system import *

""" Parse Arguments to extract data script """
parser = argparse.ArgumentParser(description='Process type of data extraction and datafile')
parser.add_argument("-f", "--datafile", help="the file from which to extract data",
                    action="store", dest="datafile", required=True)
parser.add_argument("-df", "--datafolder", help="the folder containing the datafile",
                    action="store", dest="datafolder", default="Data/")
parser.add_argument("-lf", "--logfolder", help="the folder containing the logfiles",
                    action="store", dest="logfolder", default="Logs/")
parser.add_argument("-pf", "--plotfolder", help="the folder which will contain all the output plots",
                    action="store", dest="plotfolder", default="Plots/")
parser.add_argument("-l", "--logfile", help="the logfile",
                    action="store", dest="logfile", default="log.txt")
parser.add_argument("-d", "--delimiter", help="the csv file delimiter",
                    action="store", dest="data_delimiter", default=",")
group_outlier = parser.add_mutually_exclusive_group(required=True)
group_outlier.add_argument("-mrg", "--merge", help="specify columns to include from the data file",
                    action="store_true", dest="merge_ranklists")
group_outlier.add_argument("-if", "--iforests", help="specify columns to include from the data file (default: true)",
                    action="store_true", dest="generate_iForest")
group_outlier.add_argument("-dict", "--dictated", help="specify columns to include from the data file (default: true)",
                    action="store_true", dest="dictated_outliers")
parser.add_argument("-b", "--budget", help="Number of plots to display (default 3)",
            		type=int, default='3', dest="budget")
parser.add_argument("-n", "--number", help="Number of outliers to choose (default 10)",
            		type=int, default='10', dest='num_outliers')
parser.add_argument("-p", "--pval", help="Score scaling factor (default 1.0)",
            		action="store", default='1.0', dest='p_val')
parser.add_argument("-s", "--show", help="mention if you want to show all the generated plots",
                    action="store_true", dest="output_plots")
parser.add_argument("-bs", "--baselines", help="mention if you want to run the baselines",
                    action="store_true", dest="baseline")
args = parser.parse_args()

""" Initialize Workspace """
check_environment(args)

data = read_data(args) # from data_transform.py

""" Plot Generator Helper Data """
cprint("Generating Plot Helper Data")
enable_warnings()
users = data.groupby('SOURCE')
destinations = data.groupby('DESTINATION')
print_ok("Plot Helpers Generated")

""" Scatter Plots """
rank_matrix = []
scatter_plots = 0 # Count of the number of scatter plots generated
cprint ("Generating Scatter Plots")
enable_warnings()
['SRC', 'DEST', 'EDGES_IN', 'EDGES_OUT', 'LIFE', 'MEDIAN_IAT', 'MEAN_IAT', 'IAT_VAR_MEAN']
SRC = fix_zero_error(destinations['SOURCE'].nunique().values.tolist())
DEST = fix_zero_error(users['DESTINATION'].nunique().values.tolist())
LIFE = fix_zero_error(users['LIFETIME'].first().values.tolist())
EDGES_IN = fix_zero_error(destinations['WEIGHT'].count().values.tolist())
EDGES_OUT = fix_zero_error(users['WEIGHT'].count().values.tolist())
IAT_VAR_MEAN = fix_zero_error(users['IAT_VAR_MEAN'].first().values.tolist())
MEAN_IAT = fix_zero_error(users['MEAN_IAT'].first().values.tolist())
MEDIAN_IAT = fix_zero_error(users['MEDIAN_IAT'].first().values.tolist())
IDs = [key for key, val in users['IAT_VAR_MEAN']]
DEST_IDs = [key for key, val in destinations['SOURCE']]
SRC = realign(SRC, IDs, DEST_IDs)
EDGES_IN = realign(EDGES_IN, IDs, DEST_IDs)

feature_pairs = generate_pairs(continuous_features, continuous_features + discrete_features)

pp = PdfPages(args.plotfolder + 'scatterplots.pdf')
for i, features in enumerate(feature_pairs):	
	# Generate Plot
	Y = features[0]
	X = features[1]
	fig, rank_list = scatter_plot(eval(X), eval(Y), IDs, discription[Y], discription[X], discription[Y] + ' vs ' + discription[X], compare_value[X])
	rank_matrix.append(rank_list)
	if args.output_plots:
		pp.savefig(fig)
	update_progress(i+1, len(feature_pairs))
pp.close()
scatter_plots = len(feature_pairs)
print_ok('Scatter Plots Generated')

""" PlotSPOT Algorithm """
# Get Outliers Scores if using iForests
if args.generate_iForest:
	cprint("Generating Graph File")
	features = combine_features([eval(F) for F in continuous_features + discrete_features])
	iForest(IDs, features)
	print_ok("iForest Generation Complete")

# Use outlier list if provided
if not args.generate_iForest and not args.merge_ranklists:
	N_list = [len(global_outlier_list)]

count = 0
file = open(args.logfolder + args.logfile, 'w')
for N_val in [args.num_outliers]:
	# Create graph between outliers and plots
	cprint("Generating Bipartite Graph")
	scaled_matrix, normal_matrix = ranklist.generate_graph(args, N_val, rank_matrix)
	saved_graph = Graph(scaled_matrix)
	print_ok("Graph Generated Successfully")
	# Run appropriate algorithm to get list of selected graphs
	for algo in ["LookOut", "TopK"]:
		plot_coverage = []
		for B in [args.budget]:
			if algo != "LookOut"  and not args.baseline:
				continue
			
			count += 1
			graph = copy.deepcopy(saved_graph)
			cprint("\nIteration " + str(count), RED)
			print "N_val = ", N_val, " Budget = ", B, " ALGO = ", algo
			
			start_time = time.time()
			cprint ("Running PlotSpot Algorithm")
			plots = LookOut(graph, B, algo)
			frequencies = generate_frequency_list(plots, scaled_matrix)
			print_ok("PlotSpot Complete")
			elapsed_time = time.time() - start_time

			cprint("Saving Plots")
			coverage, max_coverage = get_coverage(plots, N_val, normal_matrix)
			plot_coverage.append("{0:.3f}".format(coverage))
			print "\t-> Total Plots Generated = ",
			cprint(scatter_plots, OKBLUE)
			print "\t-> Total Plots Chosen = ",
			cprint(len(plots), OKBLUE)
			print "\t-> Coverage = ",
			cprint("{0:.3f} / {1:.3f}".format(coverage, max_coverage), OKBLUE)

			# Save selected plots in pdf
			pp = PdfPages(args.plotfolder + 'selectedplots_' + str(N_val) + "_" + str(B) + "_" + algo + '.pdf')
			for i, plot in enumerate(plots):
				fig = scatter_outliers(plot, IDs, frequencies)
				fname = 'discoveries/LBNL-{0}-{1}-{2}.png'.format(N_val, B, i)
				fig.savefig(fname)
				pp.savefig(fig)
			pp.close()
			print_ok("Plots Saved")
			
			file.write("N_val " + str(N_val) + "\tBudget " + str(B) + "\tAlgo " + algo + "\tTime Taken = " + str(elapsed_time) + "\tCoverage = "+ str(coverage) + "%" + "\n")
		print plot_coverage, max_coverage
file.close()
cprint("Finished")
