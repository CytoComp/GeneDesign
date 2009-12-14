#!/usr/bin/perl
use warnings;
use strict;
use CGI;
use GeneDesign;
use GeneDesignML;

my $query = new CGI;
print $query->header;

my @styles = qw(re ol);
gdheader("Building Block Design (length overlap)", "gdOlapDes.cgi", \@styles);

my %gapperlen   = (40 => 700, 50 => 740, 60 => 740, 70 => 720, 80 => 740, 90 => 720, 100 => 660);
my %ungapperlen = (40 => 700, 50 => 700, 60 => 750, 70 => 735, 80 => 760, 90 => 765, 100 => 750);

my $loxpsym = "ATAACTTCGTATAATGTACATTATACGAAGTTAT";
if ( ! $query->param('TARBBLLEN'))
{
	my $nucseq = $query->param('PASSNUCSEQUENCE')	?	$query->param('PASSNUCSEQUENCE')	:	$query->param('nucseq');
print <<EOM;
				<div id="notes">
					<strong>To use this module you need a nucleotide sequence at least 5kb long, a target melting temperature, and a target oligo length.</strong><br>
					If your sequence is less than 100 bp, there will only be one building block.<br>
					Remember to make the maximum assembly oligo length bigger than your assembly oligos.<br><br>
					See the <a href="$docpath/Guide/" target=\"blank\">manual</a> for more information.
				</div>
				<div id="gridgroup0">
					Sequence:<br>
					<textarea name="WHOLESEQ"  rows="6" cols="100"></textarea><br>
					Sequence Name: <input type="text" name="CHNNAM" value="" size="50" maxlength="50" /><br><br>
					Begin numbering building blocks from: <input type="text" name="STARTNUM" value="1" size="3" maxlength="3" /><br><br>
					Create overlaps of length: <input type="text" name="BBLAPLEN" value="40" size="3" maxlength="3" /><br>
					Generate Gapped Oligos? <input type="checkbox" name="GAPSWIT" value="1" checked="checked" />&nbsp;&nbsp;&nbsp;<br>
					Average Building Block Length: ~ <input type="text" name="TARBBLLEN" value="740" size="4" maxlength="3" />bp<br><br>
					Target Assembly Oligo Length: 
					<select name="TAROLILEN">
						<option value="40">40</option>
						<option value="50">50</option>
						<option selected="selected" value="60">60</option>
						<option value="70">70</option>
						<option value="80">80</option>
						<option value="90">90</option>
						<option value="100">100</option>
					</select>bp<br>
					Maximum Assembly Oligo Length: 
					<input type="text" name="MAXOLILEN" value="80" size="4" maxlength="3" />bp;<br>
					Return Assembly oligos with an overlap of Tm: <input type="text" name="TARCHNMEL" value="56" size="2" maxlength="2" />&deg;&nbsp;
					within �<input type="text" name="CHNMELTOL" value="2.5" size="3" maxlength="3" />&deg;<br><br><br><br>
					<div id="gridgroup1" align ="center" style="position:absolute; top:350;">
						<input type="submit" name=".submit" value=" Design Building Blocks " />
						<input type="hidden" name="skipall" value="yes">
					</div>
				</div>
EOM
	closer();
}

elsif($query->param('WHOLESEQ'))
{
	my $wholeseq		= cleanup($query->param('WHOLESEQ'), 0);
	my $wholelen		= length($wholeseq);
	my $startnum		= $query->param('STARTNUM');			#default is 1
	my $all_tar_bbl_len	= $query->param('TARBBLLEN');			#default is 740bp
	my $bbl_lap_len		= $query->param('BBLAPLEN');			#default is 40bp	
	my $chunk_name		= $query->param('CHNNAM');

	my %pa;			#parameters hash for the oligo cruncher
	$pa{gapswit}		=	$query->param('GAPSWIT');				#default is 1;
	$pa{tar_chn_mel}	=	$query->param(-name=>'TARCHNMEL');		#default is 56�
	$pa{tar_oli_len}	=	$query->param(-name=>'TAROLILEN');		#default is 60
	$pa{per_chn_len}	=	$pa{gapswit} == 1	?	$gapperlen{$pa{tar_oli_len}}			:	$ungapperlen{$pa{tar_oli_len}};
	$pa{tar_oli_lap}	=	$pa{gapswit} == 1	?	20										:	.5 * $pa{tar_oli_len};# these are the defaults, 12 60mers with 20bp overlaps and 20bp gaps, nongapped oligos overlap by half the oligo length
	$pa{tar_oli_gap}	=	$pa{gapswit} == 1	?	$pa{tar_oli_len}-(2*$pa{tar_oli_lap})	:	0;						# length = 2*(overlap) + gap, nongapped oligos have no gaps.
	$pa{tar_oli_num}	=	($pa{per_chn_len} - $pa{tar_oli_lap}) / ($pa{tar_oli_len} - $pa{tar_oli_lap});#18;
	$pa{chn_mel_tol}	=	$query->param(-name=>'CHNMELTOL');		#default is 2.5
	$pa{max_oli_len}	=	$query->param(-name=>'MAXOLILEN');		#default is 80
	$pa{melform}		=	3;
	
	if ($pa{max_oli_len} < $pa{tar_oli_len})
	{
		take_exception("The maximum allowable assembly oligo length ($pa{max_oli_len}) is less than the target assembly oligo length ($pa{tar_oli_len}).  Please go back and change the parameters.");
		exit;
	}
	if ($pa{max_oli_len} == $pa{tar_oli_len})
	{
		take_note("The maximum allowable assembly oligo length is equal to the target assembly oligo length ($pa{tar_oli_len}).  This may cause some weird behavior, especially in terms of overlap melting temperature.");
	}	
	if ($chunk_name !~ /^\d+[RL]\.\d+_\d+\.[A-Z]\d+$/)
	{
		take_note("Your chunk name does not conform to the expected format (chromosome)(arm).(genome version)_(chromosome version).(chunk letter)(chunk section)<br>
					I am producing output with \"$chunk_name\", but you may wish to re-run primer design with a proper name.<br>");
	}
	
	my @Olaps;
	my @Chunks;
	my $MASK = "0" x length($wholeseq);
	my @loxbounds;
	my $last;
##Mask loxpsym sites
	my $exp = regres($loxpsym, 1);
	while ($wholeseq =~ /($exp)/ig)
	{
		my $sit =  (pos $wholeseq) - length($loxpsym);
		substr($MASK, $sit, length($loxpsym)) = "1" x length($loxpsym) if ($sit ne '');
	}
	while ($MASK =~ /01/ig)
	{
		push @loxbounds, $last + int((pos($MASK) - $last)/2) if ($last > 0);
		$last = pos($MASK);
	}
	push @loxbounds, length($MASK)-21;
	
## Form chunk objects,
	if ($wholelen >1000)
	{
		my %bblen;
		my $chunkcount = 0;
		my @Olaps;
		for my $y (1..16)
		{
			$bblen{(($all_tar_bbl_len-$bbl_lap_len)*$y)+$bbl_lap_len} = $y;
		}
		for (my $x = 0;	$x < @loxbounds-1;	$x++)
		{
			my $schunkstart = $loxbounds[$x]-($bbl_lap_len/2) + 1;
			my $schunkstop = $loxbounds[$x+1]+($bbl_lap_len/2);
			my $schunklen = $schunkstop - $schunkstart + 1;
			my $thisseq = substr($wholeseq, $schunkstart, $schunklen);
			my $laststart = $schunkstart;
			my $cur = $schunkstart;
			my @posslen = sort{ abs($a-length($thisseq)) <=> abs($b-length($thisseq))} keys %bblen;
			my $tar_len = $posslen[0];
			my $tar_num = $bblen{$tar_len};
			my $tar_cur_dif = length($thisseq) - $tar_len;
			my $tar_bbl_len = $all_tar_bbl_len;
			if (abs($tar_cur_dif) >= $tar_num)
			{
				$tar_bbl_len = $tar_bbl_len + int($tar_cur_dif / $tar_num);
				$tar_cur_dif = $tar_cur_dif - ($tar_num * (int($tar_cur_dif / $tar_num)));
			}
			for my $cur (1..$tar_num)
			{
				my $cur_bbl_len = $tar_bbl_len;
				$cur_bbl_len++ if ( $cur <= abs($tar_cur_dif) && $tar_cur_dif > 0);
				$cur_bbl_len-- if ( $cur <= abs($tar_cur_dif) && $tar_cur_dif < 0);
				my $tno = new Chunk;
				my $countstr = $chunkcount + 1;
				while (length(@Chunks-0) > length($countstr))	{	$countstr = "0" . $countstr;}
				$tno->ChunkNumber($countstr);
				$cur_bbl_len++ while (substr($MASK, $laststart + $cur_bbl_len - $bbl_lap_len, $bbl_lap_len) =~ /1/);
				$tno->ChunkSeq(substr($wholeseq, $laststart, $cur_bbl_len));
				$tno->ThreePrimeOlap(substr($wholeseq, $laststart + $cur_bbl_len - $bbl_lap_len, $bbl_lap_len));
				$tno->ChunkLength(length($tno->ChunkSeq));
				$tno->ChunkStart($laststart);
				$tno->ChunkStop($tno->ChunkLength + $tno->ChunkStart - 1);
				$tno->Mask(substr($MASK, $laststart, $cur_bbl_len));
				push @Olaps, $tno->ThreePrimeOlap;
				oligocruncher($tno, \%pa);
				$laststart += $tno->ChunkLength - length($tno->ThreePrimeOlap);
				push @Chunks, $tno;
				$chunkcount++;
			}
		}
		take_note(scalar(@Chunks) . " building blocks were generated.<br>");#, int((length($wholeseq) / $tar_bbl_len)+.5), "<br><br>";
	}
	else
	{
		my $countstr = $startnum;
		while (2 > length($countstr))	{	$countstr = "0" . $countstr;}
		my $tno = new Chunk;
		$tno->ChunkNumber($countstr);
		$tno->ChunkSeq($wholeseq);
		$tno->ChunkLength($wholelen);
		$tno->ChunkStart(1);
		$tno->Mask($MASK);
		$tno->ChunkStop($tno->ChunkLength + $tno->ChunkStart - 1);
		oligocruncher($tno, \%pa);
		push @Chunks, $tno;
		take_note("1 building block was generated.<br>");#, int((length($wholeseq) / $tar_bbl_len)+.5), "<br><br>";
	}
	
		my @alloligos;
		my @aonums;
		my @bbnums;
		my @allbbs;
		my @coords;
		my @allusers;
		
## Print Sequence all Pretty for Perusal
	foreach my $tiv (@Chunks)
	{
		print "Building Block $chunk_name.", $tiv->ChunkNumber, "&nbsp;&nbsp;&nbsp;", $tiv->ChunkLength, "bp&nbsp;&nbsp;&nbsp;", $tiv->ChunkStart, "..", $tiv->ChunkStop, "\n<Br>";
		print "Three Prime Overlap: <code>", $tiv->ThreePrimeOlap, "</code><br>" if ($tiv->ChunkNumber < scalar(@Chunks));
		print "Sequence:<br>", $query->textarea(-name=>$chunk_name.$tiv->ChunkNumber, -rows=>6, -columns=>150, -value=>$tiv->ChunkSeq, -readonly=>'true');
		push @allbbs, $tiv->ChunkSeq;
		push @coords, $tiv->ChunkStart. "..". $tiv->ChunkStop;
		my @oligoarr = @{$tiv->Oligos};
		my @olaparr = @{$tiv->Olaps};
		my %colhas = %{$tiv->Collisions};
		my @colkeys = keys %colhas;
		my $prev;
		print "<br>Assembly Oligos: average overlap Tm is ", $tiv->AvgOlapMelt, "&deg;; average oligo length is ", $tiv->AvgOligoLength, "bp.<br>";
		if (@colkeys-0 != 0)
		{
			print ("<div id = \"warn\">\n");
			print "<strong>Warning:</strong> in the following building block, there are ", @colkeys-0, " collisions<br>";
			print "Try increasing the Tm tolerance for assembly oligos to remove collisions.";
			print ("</div>");
		}
		if ($pa{tar_chn_mel} - $tiv->AvgOlapMelt > 5)
		{
			print ("<div id = \"warn\">\n");
			print "<strong>Warning:</strong> in the following building block, the average overlap melting temperature is more than 5&deg; from your specified target of $pa{tar_chn_mel}&deg;.<br>";
			print "Try increasing the maximum allowable length for assembly oligos to allow oligo extension for melting temperature uniformity.";
			print ("</div>");
		}
		print_oligos_aligned($tiv, $pa{gapswit}, 4, 1);
		print break(6);
	}
	
## Offer files
	foreach my $tiv (@Chunks)
	{
		my $oliarrref = $tiv->Oligos;
		my $tcv = 1;
		push @aonums, @$oliarrref - 0;
		push @bbnums, @alloligos - 0;
		foreach (@$oliarrref)
		{
			my $seq = $_;
			$seq = complement($_, 1) if ($tcv % 2 == 0);
			chomp($seq);
			push @alloligos, $seq;
			$tcv++;
		}
	}
	
	my %hiddenhash = ("startnum" => $startnum, "bbnums" => join(" ", @bbnums), "coords" => join(" ", @coords), "aonums" => join(" ", @aonums), "alloligos" => join(" ", @alloligos), "allbbs" => join(" ", @allbbs));
	my $hiddenstring = hidden_fielder(\%hiddenhash);

print <<EOM;
			</form>
			<form name="form2" method="post" action="./order.cgi">
				<input type="hidden" name="swit" value="2" />
				<input type="hidden" name="name" value="$chunk_name" />
				FASTA format: <input type="submit" value="&nbsp;Assembly Oligos&nbsp;" onClick="FASTArizer(2)" /> <input type="submit" value="&nbsp;Building Blocks&nbsp;" onClick="FASTArizer(4)" /><br>
				tabbed format: <input type="submit" value="&nbsp;Assembly Oligos&nbsp;" onClick="FASTArizer(5)" /> <br>
				Excel file: <input type="submit" value="&nbsp;Master Order Sheet&nbsp;" onClick="FASTArizer(7)" /> <input type="submit" value="&nbsp;Individual Order Sheets&nbsp;" onClick="FASTArizer(8)" /><br>
				zip archive: <input type="submit" value="&nbsp;BB $chunk_name order sheets&nbsp;" onClick="FASTArizer(9)" /><br><br>
				$hiddenstring
EOM
	closer();
}